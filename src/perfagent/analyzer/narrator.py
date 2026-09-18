"""Narrate a finished run in plain English for stakeholders.

The narration is the ONLY place the LLM is involved in analysis, and it is given
the already-computed numbers and verdict — it explains them, it does not compute
them. If no provider is configured, a deterministic template summary is used
instead, so a report can always be produced.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from perfagent.providers.base import LLMProvider


class Narrative(BaseModel):
    """Structured narration so we can render it cleanly and keep it grounded."""

    headline: str = Field(..., description="One-sentence verdict in plain language.")
    summary: str = Field(..., description="2-4 sentences explaining what happened.")
    observations: list[str] = Field(
        default_factory=list, description="Bullet points on notable findings."
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Suggested next steps (hypotheses, not proven)."
    )


_SYSTEM = """\
You explain the results of a performance test to non-expert stakeholders. You are \
given the computed metrics and the pass/fail verdict — these are FACTS you must not \
change. Write a clear, honest, plain-language explanation.

Rules:
- Use ONLY the numbers provided. Never invent or estimate figures.
- Be plain and non-alarmist. Explain what the numbers mean in practice.
- If it passed, say so clearly. If it failed, explain which threshold and by how much.
- Recommendations are hypotheses to investigate, not proven causes. Phrase them as \
suggestions ("consider", "investigate"), never as certainties.
- Keep it concise.
"""


def _verdict_word(passed) -> str:
    if passed is True:
        return "PASS"
    if passed is False:
        return "FAIL"
    return "INCONCLUSIVE"


def _facts_block(target: str, snapshot: dict, verdict: dict) -> str:
    lat = snapshot.get("latency", {})
    lines = [
        f"Target: {target}",
        f"Total requests: {snapshot.get('requests', 0)}",
        f"Failed requests: {snapshot.get('failed', 0)}",
        f"Error rate: {snapshot.get('error_rate', 0) * 100:.2f}%",
        f"Throughput: {snapshot.get('rps', 0)} requests/sec",
        f"Latency avg: {lat.get('avg_ms', 0)} ms",
        f"Latency p50: {lat.get('p50_ms', 0)} ms",
        f"Latency p95: {lat.get('p95_ms', 0)} ms",
        f"Latency p99: {lat.get('p99_ms', 0)} ms",
        f"Latency max: {lat.get('max_ms', 0)} ms",
        "",
        f"Overall verdict: {_verdict_word(verdict.get('overall_passed'))}",
        "Threshold checks:",
    ]
    for c in verdict.get("checks", []):
        status = "PASS" if c["passed"] else "FAIL" if c["passed"] is False else "N/A"
        lines.append(
            f"  - {c['metric']} {c['op']} {c['target']} | actual {c['actual']} | {status}"
        )
    lines.append("")
    lines.append("Per-endpoint:")
    for e in snapshot.get("per_endpoint", []):
        lines.append(
            f"  - {e['name']}: {e['requests']} reqs, {e['failed']} failed, "
            f"avg {e['avg_ms']}ms, p95 {e['p95_ms']}ms"
        )
    return "\n".join(lines)


def _fallback_narrative(target: str, snapshot: dict, verdict: dict) -> Narrative:
    passed = verdict.get("overall_passed")
    lat = snapshot.get("latency", {})
    reqs = snapshot.get("requests", 0)
    err = snapshot.get("error_rate", 0) * 100
    p95 = lat.get("p95_ms", 0)

    if passed is True:
        headline = f"The test PASSED: {target} met all performance thresholds."
    elif passed is False:
        headline = f"The test FAILED: {target} missed one or more thresholds."
    else:
        headline = f"The test ran against {target}; no thresholds were evaluable."

    summary = (
        f"The system handled {reqs} requests with a {err:.2f}% error rate and a "
        f"95th-percentile latency of {p95} ms. "
    )
    failed = [c for c in verdict.get("checks", []) if c["passed"] is False]
    if failed:
        parts = [
            f"{c['metric']} was {c['actual']} (target {c['op']} {c['target']})"
            for c in failed
        ]
        summary += "Thresholds missed: " + "; ".join(parts) + "."
    else:
        summary += "All configured thresholds were satisfied."

    observations = []
    for e in snapshot.get("per_endpoint", []):
        if e["failed"] > 0:
            observations.append(
                f"{e['name']} had {e['failed']} failed request(s) out of {e['requests']}."
            )
    if not observations:
        observations.append("No endpoint returned errors during the run.")

    return Narrative(
        headline=headline,
        summary=summary,
        observations=observations,
        recommendations=[] if passed else [
            "Investigate the endpoint(s) contributing most to the missed threshold.",
        ],
    )


def narrate(
    target: str,
    snapshot: dict,
    verdict: dict,
    provider: LLMProvider | None,
) -> Narrative:
    """Produce a stakeholder narrative. Uses the LLM if available, else a fallback."""
    if provider is None:
        return _fallback_narrative(target, snapshot, verdict)

    facts = _facts_block(target, snapshot, verdict)
    user = (
        "Here are the computed results of a performance test. Write the explanation.\n\n"
        + facts
    )
    try:
        return provider.structured(response_model=Narrative, system=_SYSTEM, user=user)
    except Exception:  # noqa: BLE001
        return _fallback_narrative(target, snapshot, verdict)