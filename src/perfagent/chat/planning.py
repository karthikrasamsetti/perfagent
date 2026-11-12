"""Turn the conversation's draft into a saved plan — through the normal planner.

This is the hand-off from chat to the rest of the agent. It reuses ``draft_plan`` (so
every deterministic control still applies: forced target, code-owned load shape,
threshold sanity, correlation), stores the plan, audits it and grades it. The result
has the same shape the Review step already consumes from /api/plan and /api/chat-plan.

Nothing here fires load: the plan still has to be reviewed and approved by a human.
"""

from __future__ import annotations

from perfagent import audit, tracing
from perfagent.chat.draft import DEFAULT_DURATION_SECONDS, DEFAULT_USERS
from perfagent.chat_intent import ChatIntent
from perfagent.db import PlanRow, get_session
from perfagent.evaluation import evaluate_plan
from perfagent.plan_summary import plan_rationale, usage_summary
from perfagent.planner import PlanRequest, draft_plan
from perfagent.planner.spec import EndpointSpec
from perfagent.providers.base import LLMProvider


def plan_request_from_intent(intent: ChatIntent, fallback_goal: str = "") -> PlanRequest:
    """Map the draft onto the planner's input. Raises ValueError if it isn't usable."""
    return PlanRequest(
        target_base_url=intent.target_base_url,
        goal=intent.goal or fallback_goal[:120],
        max_users=intent.max_users or DEFAULT_USERS,
        duration_seconds=intent.duration_seconds or DEFAULT_DURATION_SECONDS,
        profile_type=intent.profile_type,
        endpoints=[
            EndpointSpec(method=e.method, path=e.path, example_body=e.example_body)
            for e in intent.endpoints
        ],
    )


def build_plan_from_intent(
    intent: ChatIntent,
    provider: LLMProvider,
    *,
    session_id: str = "",
    fallback_goal: str = "",
) -> dict:
    """Draft, save, audit and evaluate a plan. Returns the Review-step payload."""
    request = plan_request_from_intent(intent, fallback_goal)

    tracing.set_step("chat")
    plan = draft_plan(request, provider)

    with get_session() as s:
        s.add(PlanRow(
            id=plan.id,
            target_base_url=plan.load_model.target_base_url,
            goal=request.goal,
            load_model_json=plan.load_model.model_dump_json(),
        ))
        s.commit()

    usage = usage_summary(provider)
    audit.record(
        "plan.created", entity="plan", entity_id=plan.id,
        target=plan.load_model.target_base_url,
        summary=(f"Conversation-drafted a plan with "
                 f"{len(plan.load_model.scenarios)} scenario(s)"),
        tokens=usage.get("total_tokens", 0), cost_usd=usage.get("cost_usd", 0.0),
    )

    return {
        "plan_id": plan.id,
        "provider": getattr(provider, "name", ""),
        "load_model": plan.load_model.model_dump(mode="json"),
        "evaluation": evaluate_plan(plan.load_model, request).summary(),
        "rationale": plan_rationale(plan.load_model),
        "usage": usage,
        "notes": intent.notes,
        "session_id": session_id,
    }


__all__ = ["plan_request_from_intent", "build_plan_from_intent"]
