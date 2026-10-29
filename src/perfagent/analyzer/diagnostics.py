"""Deterministic diagnostics — turn a run snapshot into actionable insights.

Goes beyond PASS/FAIL: finds the slowest and most error-prone endpoints, judges
how much latency grew under load, and produces prioritized, plain-English findings
and recommendations. All computed in code (no LLM) so it's reproducible and
trustworthy — the AI narrator can then explain these findings, never invent them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Finding:
    severity: str          # "high" | "medium" | "low" | "info"
    title: str
    detail: str
    recommendation: str = ""


@dataclass
class Diagnostics:
    findings: list[Finding] = field(default_factory=list)
    slowest_endpoint: str = ""
    most_errored_endpoint: str = ""
    headline: str = ""

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "slowest_endpoint": self.slowest_endpoint,
            "most_errored_endpoint": self.most_errored_endpoint,
            "findings": [
                {"severity": f.severity, "title": f.title,
                 "detail": f.detail, "recommendation": f.recommendation}
                for f in self.findings
            ],
        }


_SEV_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def diagnose(snapshot: dict, peak_users: int | None = None) -> Diagnostics:
    """Analyze a run snapshot and return diagnostic findings (deterministic)."""
    d = Diagnostics()
    findings: list[Finding] = []

    overall_err = float(snapshot.get("error_rate", 0.0) or 0.0)
    lat = snapshot.get("latency", {}) or {}
    p95 = float(lat.get("p95_ms", 0) or 0)
    p99 = float(lat.get("p99_ms", 0) or 0)
    avg = float(lat.get("avg_ms", 0) or 0)
    mx = float(lat.get("max_ms", 0) or 0)
    eps = snapshot.get("per_endpoint", []) or []

    # ---- overall error finding ----
    if overall_err > 0:
        sev = "high" if overall_err >= 0.05 else "medium" if overall_err >= 0.01 else "low"
        findings.append(Finding(
            sev, "Requests are failing",
            f"The overall error rate is {overall_err*100:.2f}%.",
            "Investigate the failing endpoint(s) below; check auth, payloads, and server logs.",
        ))

    # ---- per-endpoint analysis: slowest + most errored ----
    if eps:
        # slowest by p95 (fall back to avg)
        def ep_p95(e):
            return float(e.get("p95_ms", e.get("avg_ms", 0)) or 0)

        def ep_err(e):
            reqs = float(e.get("requests", 0) or 0)
            failed = float(e.get("failed", 0) or 0)
            return (failed / reqs) if reqs else 0.0

        slowest = max(eps, key=ep_p95)
        d.slowest_endpoint = slowest.get("name", "")
        if ep_p95(slowest) > 0:
            # is it an outlier vs the others?
            others = [ep_p95(e) for e in eps if e is not slowest]
            avg_others = (sum(others) / len(others)) if others else ep_p95(slowest)
            ratio = (ep_p95(slowest) / avg_others) if avg_others else 1.0
            if ratio >= 2.0 and len(eps) > 1:
                findings.append(Finding(
                    "medium", "One endpoint is much slower than the rest",
                    f"'{d.slowest_endpoint}' has a p95 of {ep_p95(slowest):.0f} ms — "
                    f"about {ratio:.1f}x the average of the other endpoints.",
                    f"Profile '{d.slowest_endpoint}' — it's the main latency contributor "
                    "(check DB queries, external calls, or payload size).",
                ))
            else:
                findings.append(Finding(
                    "info", "Slowest endpoint",
                    f"'{d.slowest_endpoint}' is the slowest at p95 {ep_p95(slowest):.0f} ms.",
                ))

        # most error-prone endpoint
        errored = [e for e in eps if ep_err(e) > 0]
        if errored:
            worst = max(errored, key=ep_err)
            d.most_errored_endpoint = worst.get("name", "")
            er = ep_err(worst)
            sev = "high" if er >= 0.05 else "medium"
            findings.append(Finding(
                sev, "An endpoint is failing often",
                f"'{d.most_errored_endpoint}' failed {er*100:.1f}% of its requests "
                f"({int(worst.get('failed',0))}/{int(worst.get('requests',0))}).",
                f"Fix '{d.most_errored_endpoint}' first — it's the biggest source of errors "
                "(often auth/token, missing data, or a server-side limit).",
            ))

    # ---- latency spread / tail analysis ----
    if p95 > 0 and p99 > 0:
        tail = p99 / p95 if p95 else 1.0
        if tail >= 3.0:
            findings.append(Finding(
                "medium", "Long latency tail",
                f"p99 ({p99:.0f} ms) is {tail:.1f}x the p95 ({p95:.0f} ms) — a few requests "
                "are far slower than typical.",
                "Look for occasional slow paths: cold caches, lock contention, GC pauses, "
                "or a slow dependency hit intermittently.",
            ))
    if mx > 0 and p95 > 0 and mx >= p95 * 5:
        findings.append(Finding(
            "low", "Occasional very slow requests",
            f"The slowest request ({mx:.0f} ms) is far above the p95 ({p95:.0f} ms).",
            "Usually a rare outlier; worth checking if it correlates with a specific endpoint.",
        ))

    # ---- concurrency-impact hint ----
    # We don't have per-stage history in the snapshot, but we can flag the shape:
    # high avg vs low p50 would indicate load-driven degradation; here we use a
    # simple heuristic on the latency spread relative to the user count.
    if peak_users and peak_users > 0 and avg > 0 and p95 > 0:
        if p95 >= avg * 3 and peak_users >= 10:
            findings.append(Finding(
                "info", "Latency spreads under load",
                f"With up to {peak_users} concurrent users, p95 ({p95:.0f} ms) is well above "
                f"the average ({avg:.0f} ms), suggesting response times spread as load rose.",
                "Re-run with a higher peak to find where it degrades, or add a soak stage "
                "to see if it worsens over time.",
            ))

    # ---- all-clear ----
    if not findings:
        findings.append(Finding(
            "info", "No problems detected",
            "No failing endpoints, no unusual latency spread, and no obvious bottleneck.",
            "Consider testing at a higher user count to find the system's limit.",
        ))

    findings.sort(key=lambda f: _SEV_ORDER.get(f.severity, 9))
    d.findings = findings

    # headline = the top finding
    top = findings[0]
    if top.severity in ("high", "medium"):
        d.headline = top.title
    elif d.slowest_endpoint:
        d.headline = f"No critical issues; slowest endpoint was '{d.slowest_endpoint}'"
    else:
        d.headline = "No critical issues detected"
    return d
