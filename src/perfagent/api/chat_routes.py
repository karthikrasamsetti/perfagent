"""API routes: the multi-turn planning conversation (Conversation mode).

  GET    /api/chat/config                  is the mode enabled + its limits
  POST   /api/chat/sessions                start a conversation with a first message
  GET    /api/chat/sessions                recent conversations (newest first)
  GET    /api/chat/sessions/{id}           one conversation (resume after a refresh)
  POST   /api/chat/sessions/{id}/messages  send the next message
  POST   /api/chat/sessions/{id}/build     build a plan from the draft -> Review step
  DELETE /api/chat/sessions/{id}           forget a conversation

Every route returns the same "view": the transcript, the structured draft, what is
still missing, and (once built) the plan in the shape the Review step already uses.
The single-shot POST /api/chat-plan is unchanged.
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from perfagent import audit
from perfagent.chat import (
    ChatService,
    EmptyMessage,
    MessageTooLong,
    NotReady,
    ProviderUnavailable,
    SessionNotFound,
    TurnLimitReached,
)
from perfagent.config import get_settings
from perfagent.providers import build_provider

router = APIRouter()

_service: ChatService | None = None
_service_guard = threading.Lock()


def _provider():
    # Looked up at call time so the provider can be swapped (settings change, tests).
    return build_provider()


def get_service() -> ChatService:
    """The process-wide ChatService, created on first use."""
    global _service
    with _service_guard:
        if _service is None:
            _service = ChatService(lambda: _provider())
        return _service


def reset_service() -> None:
    """Drop the cached service (closes its checkpoint store). Used by tests."""
    global _service
    with _service_guard:
        if _service is not None:
            _service.close()
        _service = None


def _enabled_service() -> ChatService:
    if not get_settings().chat_conversation_enabled:
        raise HTTPException(status_code=404, detail="conversation mode is turned off")
    return get_service()


def _call(fn, *args):
    """Run a service call, mapping conversation errors to HTTP status codes."""
    try:
        return fn(*args)
    except (EmptyMessage, MessageTooLong, ProviderUnavailable) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SessionNotFound as e:
        raise HTTPException(status_code=404, detail="conversation not found") from e
    except NotReady as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except TurnLimitReached as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


class ChatMessageBody(BaseModel):
    message: str
    collection_text: str = ""


@router.get("/api/chat/config")
def chat_config() -> dict:
    s = get_settings()
    return {
        "enabled": s.chat_conversation_enabled,
        "max_turns": s.chat_max_turns,
        "max_message_chars": s.chat_max_message_chars,
    }


@router.post("/api/chat/sessions")
def start_session(body: ChatMessageBody) -> dict:
    view = _call(_enabled_service().start, body.message, body.collection_text)
    audit.record("chat.started", entity="chat", entity_id=view["session_id"],
                 target=view["draft"]["target_base_url"],
                 summary="Planning conversation started")
    return view


@router.get("/api/chat/sessions")
def list_sessions(limit: int = 20) -> dict:
    return {"sessions": _enabled_service().list(limit)}


@router.get("/api/chat/sessions/{session_id}")
def get_session_view(session_id: str) -> dict:
    return _call(_enabled_service().get, session_id)


@router.post("/api/chat/sessions/{session_id}/messages")
def send_message(session_id: str, body: ChatMessageBody) -> dict:
    return _call(_enabled_service().send, session_id, body.message, body.collection_text)


@router.post("/api/chat/sessions/{session_id}/build")
def build_plan(session_id: str) -> dict:
    return _call(_enabled_service().build, session_id)


@router.delete("/api/chat/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    _call(_enabled_service().delete, session_id)
    audit.record("chat.deleted", entity="chat", entity_id=session_id[:32],
                 summary="Planning conversation deleted")
    return {"deleted": session_id}
