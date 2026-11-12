"""Conversational planning — a real back-and-forth that builds the plan.

    service = ChatService(build_provider)
    view = service.start("Load test login at https://staging.example.com")
    view = service.send(view["session_id"], "50 users for 2 minutes")
    view = service.build(view["session_id"])     # -> view["plan"] goes to Review

The conversation is a LangGraph graph checkpointed per session, so it survives a
refresh or a restart. It only ever drafts a plan — a human still reviews and approves
it, and nothing here generates a script or fires load.
"""

from perfagent.chat.draft import ChatTurn, Readiness, assess, merge_intent
from perfagent.chat.graph import ChatState, build_chat_graph
from perfagent.chat.service import (
    ChatError,
    ChatService,
    EmptyMessage,
    MessageTooLong,
    NotReady,
    ProviderUnavailable,
    SessionNotFound,
    TurnLimitReached,
    make_checkpointer,
)

__all__ = [
    "ChatService", "ChatState", "ChatTurn", "Readiness", "assess", "merge_intent",
    "build_chat_graph", "make_checkpointer",
    "ChatError", "EmptyMessage", "MessageTooLong", "NotReady", "ProviderUnavailable",
    "SessionNotFound", "TurnLimitReached",
]
