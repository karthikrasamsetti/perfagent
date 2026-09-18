"""Phase-2 demo: give the agent endpoints, the AI drafts the LoadModel, then we
render a runnable script from it.

Needs a provider key set in `.env` (see .env.example). Run:
    uv run python examples/plan_and_generate.py

This is the first stage where the AI enters. Notice: the AI only produces a
*LoadModel* — the same validated contract you already had in Phase 1 — and the
generator that turns it into a script is unchanged.
"""

from __future__ import annotations

from pathlib import Path

from perfagent.generator import generate_script
from perfagent.planner import EndpointSpec, PlanRequest, draft_plan
from perfagent.providers import build_provider


def main() -> None:
    request = PlanRequest(
        target_base_url="http://127.0.0.1:8000",
        goal="A realistic load test of browsing and checkout, browsing much more common.",
        max_users=100,
        duration_seconds=240,
        endpoints=[
            EndpointSpec(method="GET", path="/products", description="List products"),
            EndpointSpec(method="POST", path="/login", description="Log in",
                         example_body={"user": "demo", "password": "x"}),
            EndpointSpec(method="POST", path="/cart", description="Add to cart",
                         example_body={"product_id": 1}),
            EndpointSpec(method="POST", path="/checkout", description="Place order",
                         example_body={"pay": "card"}),
        ],
    )

    provider = build_provider()
    print(f"Planning with provider: {provider.name} ...")

    plan = draft_plan(request, provider)
    model = plan.load_model

    print(f"\nDrafted LoadModel (plan id {plan.id}):")
    print(f"  target:   {model.target_base_url}")
    print(f"  profile:  {model.load_profile.type.value}, "
          f"peak {model.load_profile.peak_users} users, "
          f"{model.load_profile.total_seconds}s")
    print("  scenarios:")
    for sc, w in zip(model.scenarios, model.normalised_weights(), strict=False):
        steps = " -> ".join(s.path for s in sc.steps)
        print(f"    - {sc.name}  ({w:.0%})  {steps}")
    print("  thresholds:")
    for t in model.thresholds:
        print(f"    - {t.metric} {t.op} {t.value}")

    script = generate_script(plan, tool="k6")
    out = Path(__file__).parent / script.filename
    out.write_text(script.content, encoding="utf-8")
    print(f"\nWrote script: {out}  (from plan {script.plan_id})")
    print(f"Run it with:\n  locust -f {out} --host {model.target_base_url}")


if __name__ == "__main__":
    main()
