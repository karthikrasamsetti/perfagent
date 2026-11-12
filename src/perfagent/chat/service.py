"""ChatService — the conversation's application layer.

Owns the compiled graph and its checkpointer, and exposes the five things the API
needs: start, send, build, get, list (+ delete). It also:

  - masks one-way secrets in every incoming message BEFORE it enters the graph, so
    passwords/tokens/emails typed into the chat are never checkpointed to disk
    (hosts are kept readable here; the guarded provider masks them again per call);
  - enforces message-size and turn limits;
  - serialises work per conversation, so two requests can't interleave on one thread;
  - keeps a small index row (ChatSessionRow) for the "recent conversations" list.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from perfagent.chat.draft import assess, draft_view
from perfagent.chat.graph import build_chat_graph, message
from perfagent.chat.prompts import MAX_COLLECTION_CHARS
from perfagent.chat_intent import ChatIntent
from perfagent.config import Settings, get_settings
from perfagent.db import ChatSessionRow, get_session
from perfagent.guardrails.redaction import redact, restore
from perfagent.logging_config import get_logger
from perfagent.plan_summary import summarize_redactions
from perfagent.providers.base import LLMProvider

_log = get_logger("perfagent.chat")


# ---------- errors (mapped to HTTP status codes by the routes) ----------

class ChatError(Exception):
    """Base class for conversation errors."""


class EmptyMessage(ChatError):
    pass


class MessageTooLong(ChatError):
    pass


class SessionNotFound(ChatError):
    pass


class NotReady(ChatError):
    """Build was requested but essentials are still missing."""

    def __init__(self, prompts: list[str]):
        super().__init__("the draft is missing essentials: " + " ".join(prompts))
        self.prompts = prompts


class TurnLimitReached(ChatError):
    pass


class ProviderUnavailable(ChatError):
    """The LLM provider is not configured (e.g. no API key)."""


# ---------- checkpointer ----------

def make_checkpointer(path: str) -> tuple[Any, Callable[[], None]]:
    """Build the checkpoint store. Returns (saver, close).

    ":memory:" (or empty) keeps conversations in memory only. Anything else is a
    SQLite file, so conversations survive a restart. Swapping to Postgres later is
    a change here only (langgraph-checkpoint-postgres' PostgresSaver).
    """
    if not path or path == ":memory:":
        return InMemorySaver(), (lambda: None)

    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver, conn.close


# ---------- service ----------

class ChatService:
    def __init__(
        self,
        provider_factory: Callable[[], LLMProvider],
        *,
        settings: Settings | None = None,
        checkpointer: Any | None = None,
        retry_delay_seconds: float = 0.5,
    ) -> None:
        self._settings = settings or get_settings()
        self._provider_factory = provider_factory
        if checkpointer is None:
            checkpointer, self._close = make_checkpointer(self._settings.chat_checkpoint_db)
        else:
            self._close = lambda: None
        self._checkpointer = checkpointer
        self._graph = build_chat_graph(
            provider_factory,
            checkpointer,
            history_window=self._settings.chat_history_window,
            retry_delay_seconds=retry_delay_seconds,
        )
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # ---- public API -----------------------------------------------------------

    def start(self, text: str, collection_text: str = "") -> dict:
        """Open a conversation with its first message and run the first turn."""
        clean, collection, counts = self._ingest(text, collection_text)
        self._require_provider()

        session_id = uuid.uuid4().hex
        with get_session() as s:
            s.add(ChatSessionRow(id=session_id, title=clean[:80], turns=1))
            s.commit()

        entries = [message("user", clean)]
        if collection:
            entries.append(message(
                "user", f"Attached an API collection ({len(collection):,} characters).",
                kind="attachment"))
        with self._lock(session_id):
            try:
                self._graph.invoke(
                    {"messages": entries, "pending_collection": collection,
                     "turns": 1, "redactions": counts},
                    self._config(session_id),
                )
            except Exception:
                # Don't leave an index row pointing at a conversation that never started.
                with get_session() as s:
                    row = s.get(ChatSessionRow, session_id)
                    if row is not None:
                        s.delete(row)
                        s.commit()
                raise
            return self._finish(session_id)

    def send(self, session_id: str, text: str, collection_text: str = "") -> dict:
        """Add a user message to an existing conversation and run the turn."""
        clean, collection, counts = self._ingest(text, collection_text)
        with self._lock(session_id):
            state = self._state(session_id)
            if int(state.get("turns", 0)) >= self._settings.chat_max_turns:
                raise TurnLimitReached(
                    f"this conversation reached its limit of "
                    f"{self._settings.chat_max_turns} turns — build the plan or start "
                    "a new conversation")
            self._require_provider()
            self._settle(session_id)
            self._graph.invoke(
                Command(resume={"type": "message", "text": clean,
                                "collection_text": collection, "redactions": counts}),
                self._config(session_id),
            )
            return self._finish(session_id)

    def build(self, session_id: str) -> dict:
        """Build a plan from the draft. Refuses if essentials are missing."""
        with self._lock(session_id):
            state = self._state(session_id)
            readiness = assess(ChatIntent.model_validate(state.get("intent") or {}))
            if not readiness.ready:
                raise NotReady(readiness.prompts)
            self._require_provider()
            self._settle(session_id)
            self._graph.invoke(Command(resume={"type": "build"}), self._config(session_id))
            return self._finish(session_id)

    def get(self, session_id: str) -> dict:
        """The conversation as the UI shows it (used to resume after a refresh)."""
        return self._view(session_id, self._state(session_id))

    def list(self, limit: int = 20) -> list[dict]:
        """Recent conversations, newest first."""
        with get_session() as s:
            rows = (s.query(ChatSessionRow)
                    .order_by(ChatSessionRow.updated_at.desc())
                    .limit(max(1, min(limit, 100))).all())
            return [
                {
                    "session_id": r.id,
                    "title": r.title,
                    "status": r.status,
                    "turns": r.turns,
                    "plan_id": r.plan_id,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in rows
            ]

    def delete(self, session_id: str) -> None:
        """Forget a conversation: its checkpoints and its index row."""
        with self._lock(session_id):
            with get_session() as s:
                row = s.get(ChatSessionRow, session_id)
                if row is None:
                    raise SessionNotFound(session_id)
                s.delete(row)
                s.commit()
            try:
                self._checkpointer.delete_thread(session_id)
            except Exception as e:  # noqa: BLE001 — the index row is gone; log and move on
                _log.warning("chat.checkpoint_delete_failed", error=str(e))
        with self._locks_guard:
            self._locks.pop(session_id, None)

    def close(self) -> None:
        """Release the checkpoint store (closes the SQLite connection)."""
        try:
            self._close()
        except Exception:  # noqa: BLE001
            pass

    # ---- internals ------------------------------------------------------------

    def _ingest(self, text: str, collection_text: str) -> tuple[str, str, dict[str, int]]:
        """Validate a message and mask its one-way secrets before it is stored.

        Hosts are restored so the transcript stays readable; the guarded provider
        masks them again on every LLM call. Returns (message, collection, counts).
        """
        text = (text or "").strip()
        if not text:
            raise EmptyMessage("message is empty")
        if len(text) > self._settings.chat_max_message_chars:
            raise MessageTooLong(
                f"message is too long (max {self._settings.chat_max_message_chars:,} "
                "characters)")

        counts: dict[str, int] = {}

        def _mask(raw: str) -> str:
            r = redact(raw)
            for k, v in r.counts.items():
                counts[k] = counts.get(k, 0) + v
            return restore(r.text, r.mapping)

        clean = _mask(text)
        collection = (collection_text or "").strip()[:MAX_COLLECTION_CHARS]
        collection = _mask(collection) if collection else ""
        return clean, collection, counts

    def _require_provider(self) -> None:
        try:
            self._provider_factory()
        except ValueError as e:
            raise ProviderUnavailable(str(e)) from e

    def _lock(self, session_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, threading.Lock())

    @staticmethod
    def _config(session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    def _state(self, session_id: str) -> dict:
        values = self._graph.get_state(self._config(session_id)).values
        if not values:
            raise SessionNotFound(session_id)
        return values

    def _settle(self, session_id: str) -> None:
        """Make sure the graph is parked at the wait point before resuming it.

        Normally it always is. If the process died in the middle of a step, the
        checkpoint still has that step pending — run it to the wait point first, so
        the resume below is delivered to ``await_user`` and nothing is skipped.
        """
        config = self._config(session_id)
        snapshot = self._graph.get_state(config)
        if snapshot.next and not snapshot.interrupts:
            _log.info("chat.recovering_pending_step", session_id=session_id,
                      pending=list(snapshot.next))
            self._graph.invoke(None, config)

    def _finish(self, session_id: str) -> dict:
        """After a graph step: refresh the index row and return the view."""
        state = self._state(session_id)
        view = self._view(session_id, state)
        with get_session() as s:
            row = s.get(ChatSessionRow, session_id)
            if row is not None:
                row.status = view["status"]
                row.turns = int(state.get("turns", 0))
                row.plan_id = (state.get("plan") or {}).get("plan_id", "") or ""
                if not row.title and view["draft"]["goal"]:
                    row.title = view["draft"]["goal"][:80]
                s.commit()
        return view

    def _view(self, session_id: str, state: dict) -> dict:
        intent = ChatIntent.model_validate(state.get("intent") or {})
        readiness = assess(intent)
        plan = state.get("plan")
        plan_current = bool(plan) and bool(state.get("plan_current"))
        if plan_current:
            status = "planned"
        elif readiness.ready:
            status = "ready"
        else:
            status = "collecting"

        guardrail = summarize_redactions(state.get("redactions") or {})
        turns = int(state.get("turns", 0))
        return {
            "session_id": session_id,
            "status": status,
            "ready": readiness.ready,
            "messages": state.get("messages") or [],
            "draft": draft_view(intent, readiness),
            "missing": readiness.missing,
            "questions": state.get("questions") or readiness.prompts,
            "plan": ({**plan, "guardrail": guardrail} if plan else None),
            "plan_current": plan_current,
            "guardrail": guardrail,
            "usage": state.get("usage") or {},
            "tokens_total": int(state.get("tokens_total", 0)),
            "turns": turns,
            "turns_left": max(0, self._settings.chat_max_turns - turns),
            "error": state.get("last_error") or "",
        }


__all__ = [
    "ChatService", "ChatError", "EmptyMessage", "MessageTooLong", "SessionNotFound",
    "NotReady", "TurnLimitReached", "ProviderUnavailable", "make_checkpointer",
]
