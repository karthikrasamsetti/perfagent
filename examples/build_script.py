"""End-to-end Phase-1 demo: hand-written endpoint specs -> LoadModel -> Locust script.

No AI, no database. This is the whole Phase-1 core proving itself.
Run:  python examples/build_script.py
"""

from __future__ import annotations

from pathlib import Path

from perfagent.contracts import (
    LoadModel,
    LoadProfile,
    LoadProfileType,
    PlanArtifact,
    Scenario,
    Stage,
    Step,
    ThinkTime,
    Threshold,
)
from perfagent.generator import generate_script


def build_model() -> LoadModel:
    """This is what the AI Planner will produce later; for now we write it by hand."""
    browse = Scenario(
        name="browse products",
        weight=0.7,
        steps=[
            Step(name="view products", method="GET", path="/products"),
        ],
        think_time=ThinkTime(min_seconds=1, max_seconds=4),
    )
    checkout = Scenario(
        name="checkout flow",
        weight=0.3,
        steps=[
            Step(name="login", method="POST", path="/login", body={"user": "demo"}),
            Step(name="add to cart", method="POST", path="/cart", body={"product_id": 1}),
            Step(name="checkout", method="POST", path="/checkout", body={"pay": "card"}),
        ],
        think_time=ThinkTime(min_seconds=2, max_seconds=5),
    )
    profile = LoadProfile(
        type=LoadProfileType.RAMP,
        stages=[
            Stage(duration_seconds=60, target_users=20),
            Stage(duration_seconds=120, target_users=100),
            Stage(duration_seconds=60, target_users=0),
        ],
    )
    return LoadModel(
        target_base_url="http://127.0.0.1:8000",
        scenarios=[browse, checkout],
        load_profile=profile,
        thresholds=[
            Threshold(metric="p95_ms", op="<", value=800),
            Threshold(metric="error_rate", op="<", value=0.01),
        ],
    )


def main() -> None:
    plan = PlanArtifact(load_model=build_model())
    script = generate_script(plan, tool="k6")

    out = Path(__file__).parent / script.filename
    out.write_text(script.content)

    print(f"Plan id:    {plan.id}")
    print(f"Script id:  {script.id}  (from plan {script.plan_id})")
    print(f"Tool:       {script.tool}")
    print(f"Wrote:      {out}")
    print()
    print("Run it with:")
    print(f"  locust -f {out} --host http://127.0.0.1:8000")


if __name__ == "__main__":
    main()
