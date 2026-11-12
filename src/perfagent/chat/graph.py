"""The conversation graph (LangGraph).

    START -> understand -> await_user  <-----------+
                 |             |                   |
                 |             +-- message ---> understand
                 |             +-- build -----> build_plan --> await_user
                 +-- ready and the user said "go ahead" --> build_plan

  understand  one guarded LLM call returns a ChatTurn; code merges it into the draft
              and decides what is still missing.
  await_user  a LangGraph ``interrupt`` — the graph is checkpointed and stops here
              until the user sends a message or presses "Build plan". This is the same
              mechanism the approval gate will use when the run steps join the graph.
  build_plan  hands the draft to the normal planner and saves the plan for review.

The graph never generates a script and never fires load. Failures inside a node are
turned into an assistant message and the conversation carries on, so one bad LLM call
never strands a session.
"""

from __future__ import annotations

import operator
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, StateGraph
from langgraph.types import Command, interrupt

from perfagent import audit, tracing
from perfagent.chat.draft import ChatTurn, assess, merge_intent
from perfagent.chat.planning import build_plan_from_intent
from perfagent.chat.prompts import CONVERSATION_SYSTEM_PROMPT, build_turn_prompt
from perfagent.chat_intent import ChatIntent
from perfagent.logging_config import get_logger
from perfagent.plan_summary import usage_summary
from perfagent.providers.base import LLMProvider

_log = get_logger("perfagent.chat")

ProviderFactory = Callable[[], LLMProvider]


class ChatState(TypedDict, total=False):
    """Everything a conversation remembers. Plain JSON types only (checkpointed)."""

    messages: Annotated[list[dict], operator.add]  # {role, content, kind, ts}
    intent: dict               # the structured draft (ChatIntent as JSON)
    missing: list[str]         # essentials code says are still missing
    questions: list[str]       # what to ask next (code's prompts + the model's)
    ready: bool                # enough to build a plan
    wants_plan: bool           # the user asked to go ahead this turn
    plan: dict | None          # the last plan built from this conversation
    plan_current: bool         # False once the draft changed after that plan
    redactions: dict           # cumulative guardrail counts for this conversation
    usage: dict                # token usage of the last AI call
    tokens_total: int          # tokens used by this conversation so far
    turns: int                 # user turns so far
    pending_collection: str    # a pasted collection, for the next turn only
    last_error: str            # set when the last AI step failed


def message(role: str, content: str, kind: str = "text") -> dict:
    """One transcript entry."""
    return {
        "role": role,
        "content": content,
        "kind": kind,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _thread_id(config: RunnableConfig | None) -> str:
    return str(((config or {}).get("configurable") or {}).get("thread_id", ""))


def _intent_of(state: ChatState) -> ChatIntent:
    return ChatIntent.model_validate(state.get("intent") or {})


def _core(intent: ChatIntent) -> dict:
    """The part of the draft that changes the plan (ignores notes/questions)."""
    return intent.model_dump(mode="json", exclude={"needs_clarification", "notes"})


def _fallback_reply(ready: bool, prompts: list[str]) -> str:
    if ready:
        return "I have what I need. Tell me what to change, or build the plan."
    return "I still need a couple of things: " + " ".join(prompts)


def build_chat_graph(
    provider_factory: ProviderFactory,
    checkpointer: Any,
    *,
    history_window: int = 12,
    llm_attempts: int = 2,
    retry_delay_seconds: float = 0.5,
):
    """Compile the conversation graph.

    ``provider_factory`` is called inside the nodes (never stored in state), so the
    provider stays out of the checkpoint and tests can swap it freely.
    """

    def _structured_with_retry(provider: LLMProvider, user_prompt: str) -> ChatTurn:
        last: Exception | None = None
        for attempt in range(1, max(1, llm_attempts) + 1):
            try:
                return provider.structured(
                    response_model=ChatTurn,
                    system=CONVERSATION_SYSTEM_PROMPT,
                    user=user_prompt,
                )
            except Exception as e:  # noqa: BLE001 — any provider failure is retryable once
                last = e
                _log.warning("chat.llm_failed", attempt=attempt, error=f"{type(e).__name__}: {e}")
                if attempt < llm_attempts and retry_delay_seconds > 0:
                    time.sleep(retry_delay_seconds * attempt)
        assert last is not None
        raise last

    # ---- nodes ----------------------------------------------------------------

    def understand(state: ChatState, config: RunnableConfig) -> dict:
        """Read the latest user message and update the draft."""
        messages = state.get("messages") or []
        latest = messages[-1]["content"] if messages else ""
        history = messages[:-1][-history_window:]
        previous = _intent_of(state)
        was = assess(previous)

        tracing.set_step("chat")
        try:
            provider = provider_factory()
            turn = _structured_with_retry(provider, build_turn_prompt(
                intent=previous,
                missing=was.missing,
                history=[m for m in history if m.get("kind") != "error"],
                message=latest,
                collection_text=state.get("pending_collection") or "",
            ))
        except Exception as e:  # noqa: BLE001
            return {
                "messages": [message(
                    "assistant",
                    "I couldn't reach the AI just now, so nothing changed. "
                    "Send your message again in a moment.",
                    kind="error",
                )],
                "last_error": f"{type(e).__name__}: {e}"[:500],
                "wants_plan": False,
                "pending_collection": "",
            }

        merged = merge_intent(previous, turn.intent)
        now = assess(merged)
        questions = now.prompts + [q for q in merged.needs_clarification
                                   if q not in now.prompts]
        reply = (turn.reply or "").strip() or _fallback_reply(now.ready, now.prompts)

        usage = usage_summary(provider)
        tokens = int(usage.get("total_tokens", 0) or 0)
        audit.record(
            "chat.turn", entity="chat", entity_id=_thread_id(config)[:32],
            target=merged.target_base_url,
            summary=f"Conversation turn {state.get('turns', 0)}",
            tokens=tokens, cost_usd=float(usage.get("cost_usd", 0.0) or 0.0),
        )

        changed = _core(merged) != _core(previous)
        update: dict = {
            "messages": [message("assistant", reply)],
            "intent": merged.model_dump(mode="json"),
            "missing": now.missing,
            "questions": questions,
            "ready": now.ready,
            "wants_plan": bool(turn.wants_plan),
            "usage": usage,
            "tokens_total": int(state.get("tokens_total", 0)) + tokens,
            "pending_collection": "",
            "last_error": "",
        }
        if changed and state.get("plan"):
            update["plan_current"] = False
        return update

    def route_after_understand(state: ChatState) -> str:
        if state.get("ready") and state.get("wants_plan") and not state.get("last_error"):
            return "build_plan"
        return "await_user"

    def await_user(state: ChatState) -> Command:
        """Stop and wait. Resumed with {'type': 'message'|'build', ...}."""
        cmd = interrupt({"waiting_for": "user", "ready": bool(state.get("ready"))})
        kind = (cmd or {}).get("type")

        if kind == "build":
            if state.get("ready"):
                return Command(goto="build_plan")
            # Fail closed: never build from an incomplete draft, whoever asked.
            prompts = assess(_intent_of(state)).prompts
            return Command(goto="await_user", update={
                "messages": [message("assistant", _fallback_reply(False, prompts))],
            })

        # a new user message
        counts = dict(state.get("redactions") or {})
        for k, v in ((cmd or {}).get("redactions") or {}).items():
            counts[k] = counts.get(k, 0) + int(v)
        entries = [message("user", str((cmd or {}).get("text", "")))]
        collection = str((cmd or {}).get("collection_text", "") or "")
        if collection:
            entries.append(message(
                "user", f"Attached an API collection ({len(collection):,} characters).",
                kind="attachment"))
        return Command(goto="understand", update={
            "messages": entries,
            "pending_collection": collection,
            "turns": int(state.get("turns", 0)) + 1,
            "redactions": counts,
        })

    def build_plan(state: ChatState, config: RunnableConfig) -> dict:
        """Hand the draft to the planner and save the plan for review."""
        intent = _intent_of(state)
        first_user = next((m["content"] for m in state.get("messages") or []
                           if m.get("role") == "user"), "")
        try:
            provider = provider_factory()
            plan = build_plan_from_intent(
                intent, provider,
                session_id=_thread_id(config), fallback_goal=first_user,
            )
        except Exception as e:  # noqa: BLE001
            _log.warning("chat.build_failed", error=f"{type(e).__name__}: {e}")
            return {
                "messages": [message(
                    "assistant",
                    "I couldn't draft the plan just now. Your draft is safe — "
                    "try Build plan again in a moment.",
                    kind="error",
                )],
                "last_error": f"{type(e).__name__}: {e}"[:500],
                "wants_plan": False,
            }

        scenarios = len(plan["load_model"].get("scenarios") or [])
        tokens = int((plan.get("usage") or {}).get("total_tokens", 0) or 0)
        return {
            "messages": [message(
                "assistant",
                f"Plan drafted with {scenarios} scenario{'s' if scenarios != 1 else ''}. "
                "Review and approve it on the next step — nothing runs until you do.",
                kind="plan",
            )],
            "plan": plan,
            "plan_current": True,
            "wants_plan": False,
            "usage": plan.get("usage") or {},
            "tokens_total": int(state.get("tokens_total", 0)) + tokens,
            "last_error": "",
        }

    # ---- wiring ---------------------------------------------------------------

    g = StateGraph(ChatState)
    g.add_node("understand", understand)
    g.add_node("await_user", await_user, destinations=("understand", "build_plan", "await_user"))
    g.add_node("build_plan", build_plan)
    g.add_edge(START, "understand")
    g.add_conditional_edges("understand", route_after_understand,
                            {"build_plan": "build_plan", "await_user": "await_user"})
    g.add_edge("build_plan", "await_user")
    return g.compile(checkpointer=checkpointer)


__all__ = ["ChatState", "build_chat_graph", "message"]
