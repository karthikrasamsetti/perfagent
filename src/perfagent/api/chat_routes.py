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
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import json
from perfagent.api.projects import require_project
from perfagent.db import get_session, PlanRow, ChatSessionRow

from perfagent import audit
from perfagent.api.docs import doc
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
    project_id: str | None = None
    test_name: str = Field(default="", max_length=120)


def _project_view(view):
    with get_session() as s:
        row = s.get(ChatSessionRow, view["session_id"])
        if row and view.get("plan"):
            plan = s.get(PlanRow, view["plan"]["plan_id"])
            if plan:
                model = json.loads(plan.load_model_json)
                if row.project_id and plan.project_id != row.project_id:
                    plan.project_id = row.project_id
                    model["test_name"] = row.test_name or model.get("test_name", "")
                    plan.load_model_json = json.dumps(model)
                    s.commit()
                view["plan"]["load_model"] = model
                view["plan"]["review_sources"] = json.loads(plan.review_sources_json) if plan.review_sources_json else None
    return view


@router.get("/api/chat/config", **doc("GET", "/api/chat/config"))
def chat_config() -> dict:
    s = get_settings()
    return {
        "enabled": s.chat_conversation_enabled,
        "max_turns": s.chat_max_turns,
        "max_message_chars": s.chat_max_message_chars,
    }


@router.post("/api/chat/sessions", **doc("POST", "/api/chat/sessions"))
def start_session(body: ChatMessageBody) -> dict:
    with get_session() as s:
        project_id = require_project(s, body.project_id)
        s.commit()
    view = _call(_enabled_service().start, body.message, body.collection_text)
    with get_session() as s:
        row = s.get(ChatSessionRow, view["session_id"])
        if row:
            row.project_id, row.test_name = project_id, body.test_name
            s.commit()
    audit.record("chat.started", entity="chat", entity_id=view["session_id"],
                 target=view["draft"]["target_base_url"],
                 summary="Planning conversation started")
    return _project_view(view)


@router.get("/api/chat/sessions", **doc("GET", "/api/chat/sessions"))
def list_sessions(limit: int = 20, project_id: str | None = None) -> dict:
    return {"sessions": _enabled_service().list(limit, project_id)}


@router.get("/api/chat/sessions/{session_id}", **doc("GET", "/api/chat/sessions/{session_id}"))
def get_session_view(session_id: str) -> dict:
    return _project_view(_call(_enabled_service().get, session_id))


@router.post("/api/chat/sessions/{session_id}/messages", **doc("POST", "/api/chat/sessions/{session_id}/messages"))
def send_message(session_id: str, body: ChatMessageBody) -> dict:
    return _project_view(_call(_enabled_service().send, session_id, body.message, body.collection_text))


@router.post("/api/chat/sessions/{session_id}/build", **doc("POST", "/api/chat/sessions/{session_id}/build"))
def build_plan(session_id: str) -> dict:
    return _project_view(_call(_enabled_service().build, session_id))


@router.delete("/api/chat/sessions/{session_id}", **doc("DELETE", "/api/chat/sessions/{session_id}"))
def delete_session(session_id: str) -> dict:
    _call(_enabled_service().delete, session_id)
    audit.record("chat.deleted", entity="chat", entity_id=session_id[:32],
                 summary="Planning conversation deleted")
    return {"deleted": session_id}
