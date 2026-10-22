"""The Planner: turn a PlanRequest into a validated LoadModel (a PlanArtifact).

Flow:
  1. Build the prompt from the request.
  2. Ask the provider for a LoadModel (Instructor validates it against the schema).
  3. Apply deterministic controls in code — never trusted to the LLM:
       - force the target URL to exactly what was requested
       - replace the load-profile SHAPE with a deterministic ramp
       - collapse duplicate/near-identical scenarios (no fake journeys from thin input)
       - sanity-fix nonsensical thresholds (e.g. "error rate < 100%")
       - auto-add an Authorization header when a token is captured (correlation)
  4. Wrap it as a PlanArtifact ready for the Generator.
"""

from __future__ import annotations

from perfagent.contracts.artifacts import PlanArtifact
from perfagent.contracts.load_model import LoadModel, Threshold
from perfagent.planner.profile import build_profile
from perfagent.planner.prompts import SYSTEM_PROMPT, build_user_prompt
from perfagent.planner.spec import PlanRequest
from perfagent.providers.base import LLMProvider


def _captured_vars(model: LoadModel) -> set[str]:
    out: set[str] = set()
    for sc in model.scenarios:
        for st in sc.steps:
            for ex in getattr(st, "extract", []) or []:
                out.add(ex.var)
    return out


def _step_signature(scenario) -> tuple:
    """A signature of what a scenario actually does — (method, path) for each step."""
    return tuple((st.method.value, st.path) for st in scenario.steps)


def _collapse_duplicate_scenarios(model: LoadModel) -> LoadModel:
    """Merge scenarios that do the same thing, so the AI can't invent fake journeys.

    Example: given only /login, the AI may produce 'Browsing' and 'Checkout' that both
    just hit /login. That's not two journeys — it's one. We keep the first, sum the
    weights, and drop the duplicates.
    """
    seen: dict[tuple, int] = {}   # signature -> index in kept list
    kept = []
    for sc in model.scenarios:
        sig = _step_signature(sc)
        if sig in seen:
            kept[seen[sig]].weight += sc.weight     # fold weight into the kept one
        else:
            seen[sig] = len(kept)
            kept.append(sc)
    # if we collapsed everything to one scenario, give it a clear generic name
    if len(kept) == 1 and len(model.scenarios) > 1:
        kept[0].name = kept[0].name or "Main journey"
    model.scenarios = kept
    return model


# Sensible bounds for threshold sanity-fixing.
_LATENCY_METRICS = {"p50_ms", "p90_ms", "p95_ms", "p99_ms", "avg_ms", "median_ms", "max_ms"}


def _sanitize_thresholds(model: LoadModel) -> LoadModel:
    """Fix or drop nonsensical thresholds so the pass/fail criteria are meaningful."""
    fixed: list[Threshold] = []
    seen_metrics: set[str] = set()
    for th in model.thresholds:
        if th.metric in seen_metrics:
            continue  # drop duplicate metric
        seen_metrics.add(th.metric)

        if th.metric == "error_rate":
            # error_rate is a fraction 0..1. "< 1" (100%) or "< 0" is meaningless.
            if th.op in ("<", "<="):
                if th.value >= 1.0 or th.value <= 0.0:
                    th.value = 0.05          # default: under 5% errors
            # keep sensible ones as-is
            fixed.append(th)
        elif th.metric in _LATENCY_METRICS:
            # latency must be a positive number of ms
            if th.value <= 0:
                th.value = 500.0
            fixed.append(th)
        else:
            # unknown metric — drop it (the verdict would be INCONCLUSIVE otherwise)
            continue

    # ensure at least a basic, meaningful pass criterion exists
    if not any(t.metric == "error_rate" for t in fixed):
        fixed.append(Threshold(metric="error_rate", op="<", value=0.05))
    if not any(t.metric in _LATENCY_METRICS for t in fixed):
        fixed.append(Threshold(metric="p95_ms", op="<=", value=500))

    model.thresholds = fixed
    return model


def _apply_deterministic_controls(model: LoadModel, request: PlanRequest) -> LoadModel:
    # 1. Target is exactly what was requested.
    model.target_base_url = request.target_base_url

    # 2. Deterministic ramp shape sized to the guard rails.
    model.load_profile = build_profile(
        profile_type=model.load_profile.type,
        peak_users=request.max_users,
        total_seconds=request.duration_seconds,
    )

    # 3. Collapse duplicate/near-identical scenarios (no fake journeys from thin input).
    model = _collapse_duplicate_scenarios(model)

    # 4. Make thresholds meaningful.
    model = _sanitize_thresholds(model)

    # 5. Auto-add the Authorization header when a token is captured (correlation).
    if "token" in _captured_vars(model):
        headers = dict(model.headers or {})
        if not any(k.lower() == "authorization" for k in headers):
            headers["Authorization"] = "Bearer ${token}"
            model.headers = headers

    return model


def draft_plan(request: PlanRequest, provider: LLMProvider) -> PlanArtifact:
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