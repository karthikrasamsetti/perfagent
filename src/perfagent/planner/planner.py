"""The Planner: turn a PlanRequest into a validated LoadModel (a PlanArtifact).

Flow:
  1. Build the prompt from the request.
  2. Ask the provider for a LoadModel (Instructor guarantees it validates against
     the schema, retrying the model if needed).
  3. Apply deterministic control in code - the LLM's draft is never trusted for the
     things code should own:
       - the target URL is forced to exactly what was requested
       - the LOAD PROFILE SHAPE (ramp up -> steady -> ramp down) is REPLACED with a
         deterministic profile built from the requested peak users + duration
  4. Wrap it as a PlanArtifact (with lineage identity) ready for the Generator.

The AI decides what journeys to test and their weights (judgement). Code owns the
target, the limits, and the shape of the load over time.
"""

from __future__ import annotations

from perfagent.contracts.artifacts import PlanArtifact
from perfagent.contracts.load_model import LoadModel
from perfagent.planner.profile import build_profile
from perfagent.planner.prompts import SYSTEM_PROMPT, build_user_prompt
from perfagent.planner.spec import PlanRequest
from perfagent.providers.base import LLMProvider


def _apply_deterministic_controls(model: LoadModel, request: PlanRequest) -> LoadModel:
    """Force the parts code must own: target URL and the load-profile shape."""
    # 1. Target is exactly what was requested (never trust a drafted URL).
    model.target_base_url = request.target_base_url

    # 2. Replace the AI's stages with a proper deterministic profile
    #    (ramp up -> steady -> ramp down) sized to the requested guard rails.
    model.load_profile = build_profile(
        profile_type=model.load_profile.type,
        peak_users=request.max_users,
        total_seconds=request.duration_seconds,
    )
    return model


def draft_plan(request: PlanRequest, provider: LLMProvider) -> PlanArtifact:
    """Draft a LoadModel for the given request using the given provider."""
    system = SYSTEM_PROMPT
    user = build_user_prompt(request)

    model: LoadModel = provider.structured(
        response_model=LoadModel,
        system=system,
        user=user,
    )

    model = _apply_deterministic_controls(model, request)
    return PlanArtifact(load_model=model)


__all__ = ["draft_plan", "PlanRequest"]