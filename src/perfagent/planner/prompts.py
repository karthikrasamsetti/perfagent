"""Prompt construction for the Planner.

The system prompt encodes the discipline: draft a realistic plan, respect the
guard rails, and stay inside the LoadModel schema. The user prompt is just the
concrete endpoints and goal. Keeping prompts here (not inline) makes them easy to
review and tune.
"""

from __future__ import annotations

from perfagent.planner.spec import PlanRequest

SYSTEM_PROMPT = """\
You are a performance-testing planner. Given a target and its endpoints, you draft \
a LoadModel: a structured plan describing which user journeys to test, how traffic \
is split between them, how load ramps over time, and the pass/fail thresholds.

Rules you must follow:
- Group endpoints into a few realistic user journeys (scenarios), not one scenario \
per endpoint. For example, browsing and checkout are separate journeys.
- Give each scenario a weight reflecting how common that journey is in real use \
(browsing is usually far more common than checkout).
- Order the steps in each scenario the way a real user would perform them \
(e.g. log in before checking out).
- Choose a load profile (ramp / spike / soak / stress) that fits the stated goal, \
and stay within the given max_users and duration_seconds.
- Set sensible think times between steps (seconds a real user pauses).
- When an endpoint has an example body, use it (or a realistic variation) as the \
step's body so POST/PUT/PATCH requests send real data.
- Include a couple of reasonable thresholds (e.g. p95 latency, error rate).
- Only use the endpoints provided. Do not invent paths.
- Do not worry about the load ramp shape or exact user counts - those are set \
separately. Focus on the journeys, their order, weights, think times, and bodies.
- Return only the structured LoadModel. Do not add commentary.
"""


def build_user_prompt(request: PlanRequest) -> str:
    lines: list[str] = []
    lines.append(f"Target base URL: {request.target_base_url}")
    lines.append(f"Goal: {request.goal}")
    lines.append(f"Guard rails: max_users={request.max_users}, "
                 f"duration_seconds={request.duration_seconds}")
    lines.append("")
    lines.append("Endpoints:")
    for e in request.endpoints:
        desc = f" - {e.description}" if e.description else ""
        body = f" (example body: {e.example_body})" if e.example_body else ""
        lines.append(f"  {e.method.value} {e.path}{desc}{body}")
    lines.append("")
    lines.append(
        "Draft a LoadModel with target_base_url set exactly to the target above, "
        "grouping these endpoints into realistic weighted scenarios, a load profile "
        "within the guard rails, and appropriate thresholds."
    )
    return "\n".join(lines)