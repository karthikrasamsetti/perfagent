"""Evaluate the quality of an AI-drafted plan — deterministically.

These checks grade the Planner's output against ground truth (the endpoints that
were actually supplied), never against "does it sound good". Each check returns a
pass/fail with a reason, and the module rolls them into a grounding score.

This is the "how do we know the AI did a good job" answer for planning: the AI can
only propose a plan a human approves, and these checks catch a bad proposal
(invented endpoints, nonsensical weights) before a human even looks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from perfagent.contracts.load_model import LoadModel
from perfagent.planner.spec import PlanRequest


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class PlanEvaluation:
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def score(self) -> float:
        """Fraction of checks passed, 0.0–1.0."""
        return (self.passed / self.total) if self.total else 1.0

    @property
    def grounded(self) -> bool:
        """True only if every check passed."""
        return all(c.passed for c in self.checks)

    def summary(self) -> dict:
        return {
            "grounded": self.grounded,
            "score": round(self.score, 3),
            "passed": self.passed,
            "total": self.total,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail}
                for c in self.checks
            ],
        }


def _norm(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


def evaluate_plan(model: LoadModel, request: PlanRequest) -> PlanEvaluation:
    """Grade a drafted LoadModel against the endpoints/target that were supplied."""
    checks: list[Check] = []

    # 1. Every step's endpoint must exist in the supplied endpoints (no invention).
    allowed = {_norm(e.method.value, e.path) for e in request.endpoints}
    allowed_paths = {e.path for e in request.endpoints}
    invented = []
    for sc in model.scenarios:
        for st in sc.steps:
            key = _norm(st.method.value, st.path)
            # accept exact method+path, or same path (method may differ sensibly)
            if key not in allowed and st.path not in allowed_paths:
                invented.append(key)
    checks.append(
        Check(
            "no_invented_endpoints",
            passed=not invented,
            detail="all endpoints supplied" if not invented
            else f"invented: {', '.join(sorted(set(invented)))}",
        )
    )

    # 2. Target URL matches what was requested (code forces this, so it should hold).
    checks.append(
        Check(
            "target_matches_request",
            passed=model.target_base_url == request.target_base_url,
            detail=model.target_base_url,
        )
    )

    # 3. At least one scenario, each with at least one step.
    ok_structure = bool(model.scenarios) and all(sc.steps for sc in model.scenarios)
    checks.append(
        Check("has_scenarios_with_steps", passed=ok_structure,
              detail=f"{len(model.scenarios)} scenario(s)")
    )

    # 4. Weights are all positive.
    ok_weights = all(sc.weight > 0 for sc in model.scenarios)
    checks.append(
        Check("weights_positive", passed=ok_weights,
              detail="all weights > 0" if ok_weights else "found non-positive weight")
    )

    # 5. Think times are sane (min <= max, both >= 0) for every scenario.
    ok_think = all(
        sc.think_time.min_seconds >= 0
        and sc.think_time.max_seconds >= sc.think_time.min_seconds
        for sc in model.scenarios
    )
    checks.append(
        Check("think_times_valid", passed=ok_think,
              detail="min<=max, non-negative" if ok_think else "invalid think time")
    )

    # 6. Load profile stays within the requested guard rails.
    peak_ok = model.load_profile.peak_users <= request.max_users
    dur_ok = model.load_profile.total_seconds <= request.duration_seconds
    checks.append(
        Check("within_guardrails", passed=peak_ok and dur_ok,
              detail=f"peak {model.load_profile.peak_users}<= {request.max_users}, "
                     f"dur {model.load_profile.total_seconds}<= {request.duration_seconds}")
    )

    return PlanEvaluation(checks=checks)