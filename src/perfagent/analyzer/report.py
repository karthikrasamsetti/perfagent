# ruff: noqa: E501
"""Render a finished run into a self-contained HTML report for stakeholders.

Pure templating over the deterministic verdict + metrics + the narrative. The
result is a single HTML file that opens in any browser and can be emailed.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from math import isfinite

from perfagent.analyzer.narrator import Narrative
from perfagent.analyzer.report_evidence import report_evidence
from perfagent.analyzer.verdict import format_threshold_value


def _badge(passed) -> str:
    if passed is True:
        return '<span class="badge pass">PASS</span>'
    if passed is False:
        return '<span class="badge fail">FAIL</span>'
    return '<span class="badge na">INCONCLUSIVE</span>'


def _timeline_charts(samples: list[dict], phases: list[dict], dropped: dict | None = None,
                     baseline_samples: list[dict] | None = None) -> str:
    def finite(value):
        return type(value) in (int, float) and isfinite(value) and value >= 0

    recorded = [sample for sample in samples if finite(sample.get("t"))]
    baseline = [sample for sample in baseline_samples or [] if finite(sample.get("t"))]
    if not recorded and not baseline:
        return ""
    end = max(sample["t"] for sample in recorded + baseline)
    duration = end or 1
    boundaries = "".join(
        f'<i class="phase-line" style="left:{phase["end_s"] / duration * 100:.4f}%"></i>'
        for phase in phases if finite(phase.get("end_s")) and 0 < phase["end_s"] < end
    )
    if dropped:
        position = dropped["elapsed_s"] / duration * 100
        boundaries += f'<i class="phase-line drop-line" style="left:{position:.4f}%"></i>'
    charts = []
    for label, key in (("Throughput (requests/s)", "rps"), ("p95 latency (ms)", "p95"), ("Error rate (%)", "err")):
        points = [(sample["t"], sample[key]) for sample in recorded if finite(sample.get(key))]
        reference = [(sample["t"], sample[key]) for sample in baseline if finite(sample.get(key))]
        if not points and not reference:
            charts.append(f"<figure><figcaption>{label}</figcaption><p>No measurements recorded.</p></figure>")
            continue
        maximum = max(value for _, value in points + reference) or 1
        dots = "".join(
            f'<i style="left:{time / duration * 100:.4f}%;bottom:{value / maximum * 100:.4f}%"></i>'
            for time, value in points
        )
        dots += "".join(
            f'<i class="reference-point" style="left:{time / duration * 100:.4f}%;bottom:{value / maximum * 100:.4f}%"></i>'
            for time, value in reference
        )
        charts.append(
            f'<figure><figcaption>{label}</figcaption><div class="chart-scale" aria-hidden="true">'
            f'{maximum:.4g}<div class="timeline-chart">{boundaries}{dots}</div>'
            f'<span>0 seconds</span><span>{end:.4g} seconds</span></div></figure>'
        )
    return '<div class="timeline-charts">' + "".join(charts) + "</div>"


def _release_section(decision: dict | None) -> str:
    if not decision:
        return ""
    escape = html.escape

    def number(value, unit):
        return f"{value:.6g} {escape(unit)}" if value is not None else "Unavailable"

    label = {"ready": "Ready", "blocked": "Blocked", "needs_evidence": "Needs evidence"}[decision["status"]]
    rules = "".join(
        f"<tr><th scope='row'>{escape(rule['name'])}</th><td>{number(rule['actual'], rule['unit'])}</td>"
        f"<td>{escape(rule['op'])} {number(rule['limit'], rule['unit'])}</td>"
        f"<td>{'Met' if rule['passed'] is True else 'Breached' if rule['passed'] is False else 'Unavailable'}</td></tr>"
        for rule in decision.get("rules", [])
    )
    table = (
        "<div class='table-scroll'><table aria-label='Release budget results'><thead><tr>"
        "<th scope='col'>Budget</th><th scope='col'>Measured</th><th scope='col'>Limit</th>"
        "<th scope='col'>Result</th></tr></thead><tbody>" + rules + "</tbody></table></div>"
        if rules else ""
    )
    scope = ""
    if decision.get("baseline_id"):
        baseline = decision.get("baseline_release") or decision["baseline_id"][:8]
        candidate = decision.get("candidate_release") or decision["candidate_id"][:8]
        scope = f"<p>Environment {escape(decision['environment'] or 'Unlabeled')} · Baseline {escape(baseline)}"
        if decision["candidate_id"] != decision["baseline_id"]:
            scope += f" · Candidate {escape(candidate)}"
        scope += "</p>"
    comparison = decision.get("comparison") or {}
    endpoints = "".join(
        f"<tr><th scope='row'>{escape(item['name'])}</th><td>{number(item['baseline_ms'], 'ms')}</td>"
        f"<td>{number(item['candidate_ms'], 'ms')}</td>"
        f"<td>{number(item['candidate_ms'] - item['baseline_ms'], 'ms')}</td></tr>"
        for item in comparison.get("endpoints", [])
    )
    endpoint_table = (
        "<div class='table-scroll'><table aria-label='Endpoint p95 changes'><thead><tr>"
        "<th scope='col'>Endpoint</th><th scope='col'>Baseline p95</th><th scope='col'>Candidate p95</th>"
        "<th scope='col'>Change</th></tr></thead><tbody>" + endpoints + "</tbody></table></div>"
        if endpoints else ""
    )
    load = ""
    if decision.get("candidate_rps") is not None:
        load = f"<p>Average load {number(decision['candidate_rps'], 'req/s')}"
        if decision.get("target_rps") is not None:
            load += f" · Planned {number(decision['target_rps'], 'req/s')}"
        load += "</p>"
    overlay = _timeline_charts(comparison.get("candidate", []), comparison.get("phases", []),
                               baseline_samples=comparison.get("baseline"))
    if overlay:
        overlay = ("<h3>Baseline versus candidate</h3>"
                   "<p>Gray squares mark the approved baseline. Purple circles mark the candidate.</p>"
                   + overlay)
    summary = f"<p>{escape(decision['summary'])}</p>" if decision.get("summary") else ""
    return (f"<section class='release-readiness'><h2>Release readiness · {label}</h2>"
            f"<p class='release-headline'>{escape(decision['reason'])}</p>{summary}{scope}{load}{table}{overlay}{endpoint_table}</section>")


def render_report_html(
    *,
    target: str,
    tool: str,
    snapshot: dict,
    verdict: dict,
    narrative: Narrative,
    plan_id: str = "",
    run_id: str = "",
    execution: dict | None = None,
    status: str | None = None,
    samples: list[dict] | None = None,
    release_readiness: dict | None = None,
    server_metrics: dict | None = None,
) -> str:
    release_explanation = (release_readiness or {}).get("explanation")
    report_summary = release_explanation or narrative.summary
    lat = snapshot.get("latency", {})
    execution = execution or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    esc = html.escape
    evidence = report_evidence({"execution": execution, "snapshot": snapshot, "verdict": verdict,
                                "status": status, "samples": samples})
    threshold_count = evidence["total_thresholds"]
    threshold_note = (f"{evidence['passed_count']} of {threshold_count} thresholds passed"
                      if threshold_count else "No threshold outcomes were recorded.")
    partial_note = "<p>The run ended early. Measurements are partial.</p>" if evidence["partial"] else ""

    def measurement(value: float | None) -> str:
        return f"{value:.4g}" if value is not None else "Unavailable"

    service_rows = "".join(
        f'<tr><th scope="row">{esc(metric["name"])}</th>'
        f'<td>{measurement(metric.get("baseline_mean"))}</td>'
        f'<td>{measurement(metric.get("run_mean"))}</td></tr>'
        for metric in (server_metrics or {}).get("metrics", [])
    )
    service_section = (
        '<h2>Service metrics</h2><table><thead><tr><th>Metric</th>'
        '<th>Before run (2 min)</th><th>During run</th></tr></thead>'
        f'<tbody>{service_rows}</tbody></table>' if service_rows else ""
    )
    checks_rows = "".join(
        f"<tr><td>{esc(c['metric'])}</td><td>{esc(c['op'])} "
        f"{esc(format_threshold_value(c['metric'], c['target']))}</td>"
        f"<td>{esc(format_threshold_value(c['metric'], c['actual']))}</td>"
        f"<td>{_badge(c['passed'])}</td></tr>"
        for c in evidence["thresholds"]
    )
    def cell(value) -> str:
        return esc(str(value)) if value is not None else "Unavailable"

    def rate(value) -> str:
        return f"{value * 100:.2f}%" if value is not None else "Unavailable"

    def latency(value) -> str:
        return f"{value} ms" if value is not None else "Unavailable"

    def rows(records, keys):
        return "".join(
            "<tr>" + "".join(f"<td>{cell(record.get(key))}</td>" for key in keys) + "</tr>"
            for record in records
        )

    throughput = cell(evidence["metrics"]["rps"])
    if evidence["metrics"]["target_rps"] is not None:
        throughput += " / " + cell(evidence["metrics"]["target_rps"])
    planned_rate = execution.get("planned_iteration_rate")
    rate_note = ""
    if not execution.get("script_edited") and planned_rate is not None:
        rate_note = f"<p>Planned journey starts/s {cell(round(planned_rate, 4))}"
        if execution.get("requests_per_iteration"):
            rate_note += f" · HTTP requests per journey {cell(execution['requests_per_iteration'])}"
        rate_note += "</p>"

    ep_rows = "".join(
        f"<tr><td>{cell(e.get('name'))}</td><td>{cell(e.get('requests'))}</td><td>{cell(e.get('failed'))}</td>"
        f"<td>{latency(e.get('avg_ms'))}</td><td>{latency(e.get('p95_ms'))}</td><td>{cell(e.get('checks_failed'))}</td>"
        f"<td>{cell(', '.join(f'{code}: {count}' for code, count in sorted((e.get('status_codes') or {}).items())) or None)}</td></tr>"
        for e in snapshot.get("per_endpoint", [])
    )
    journey_rows = rows(snapshot.get("per_journey", []), (
        "name", "requests", "failed", "iterations", "dropped_iterations", "checks_failed"))
    response_checks = rows(snapshot.get("checks", []), ("name", "passed", "failed"))
    sample_rows = rows(samples or [], ("t", "rps", "p95", "err", "dropped_iterations"))
    dropped = evidence["first_dropped_sample"]
    drop_note = (f"First recorded dropped iterations at {dropped['elapsed_s']} s "
                 f"({dropped['count']} cumulative)." if dropped else
                 "Timing is unavailable for the dropped iterations recorded in this run."
                 if snapshot.get("dropped_iterations") else "")
    phases = execution.get("planned_phases") or []
    phase_note = " · ".join(
        f"{cell(phase.get('label'))} {cell(phase.get('start_s'))}–{cell(phase.get('end_s'))} s" for phase in phases
    )
    timeline_charts = _timeline_charts(samples or [], phases, dropped)
    timing_rows = rows(
        ({"endpoint": endpoint.get("name"), "phase": name.replace("_", " "), **values}
         for endpoint in snapshot.get("per_endpoint", [])
         for name, values in (endpoint.get("timing_phases") or {}).items()),
        ("endpoint", "phase", "avg_ms", "p95_ms"),
    )
    metadata = " &nbsp;|&nbsp; ".join(
        f"{label} {cell(execution[key])}"
        for key, label in (("test_name", "Test"), ("environment", "Environment"),
                           ("release_label", "Release"), ("mode", "Mode"))
        if execution.get(key)
    )
    obs = "".join(f"<li>{esc(o)}</li>" for o in narrative.observations)
    recs = "".join(f"<li>{esc(r)}</li>" for r in narrative.recommendations)
    recs_block = f"<h2>Recommendations</h2><ul>{recs}</ul>" if recs else ""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"/>
<title>Performance Test Report</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
          color:#1f2421; max-width:820px; margin:32px auto; padding:0 20px; line-height:1.55; }}
  h1 {{ font-size:34px; letter-spacing:-.035em; margin-bottom:4px; }}
  h2 {{ font-size:16px; color:#0a4f3e; margin-top:28px; border-bottom:1px solid #e2e0d8; padding-bottom:4px; }}
  .meta {{ color:#6b6a64; font-size:13px; }}
  .headline {{ font-size:17px; margin:16px 0; padding:14px 16px; border-radius:8px;
               background:#f1efe8; border-left:5px solid #0f6e56; }}
  .badge {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:600; }}
  .badge.pass {{ background:#e1f5ee; color:#0a4f3e; }}
  .badge.fail {{ background:#faeaea; color:#a32d2d; }}
  .badge.na {{ background:#f1efe8; color:#6b6a64; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; margin-top:8px; }}
  th, td {{ text-align:left; padding:7px 10px; border-bottom:1px solid #e9e7df; }}
  th {{ background:#0f6e56; color:#fff; font-weight:500; }}
  .table-scroll {{ overflow-x:auto; }}
  .release-readiness {{ padding:16px; margin-block:16px; border:1px solid #dce2eb; border-radius:14px; background:#f4f6fc; }}
  .release-readiness h2 {{ margin-top:0; }}
  .release-headline {{ font-size:1.55rem; line-height:1.22; letter-spacing:-.03em; font-weight:680; }}
  .grid {{ display:flex; gap:28px; flex-wrap:wrap; margin:12px 0; }}
  .kpi .v {{ font-size:22px; font-weight:700; color:#0a4f3e; }}
  .kpi .l {{ font-size:12px; color:#6b6a64; }}
  ul {{ margin:8px 0; }}
  .timeline-charts {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }}
  .timeline-charts figure {{ margin:0; padding:12px; border:1px solid #e2e0d8; break-inside:avoid; }}
  .timeline-charts figcaption {{ font-weight:650; font-size:13px; }}
  .chart-scale {{ font-size:11px; }}
  .chart-scale span:last-child {{ float:right; }}
  .timeline-chart {{ position:relative; height:80px; margin:4px 3px; border-bottom:1px solid #777; }}
  .timeline-chart i {{ position:absolute; width:4px; height:4px; color:#5545bb; background:currentColor; border-radius:50%; transform:translate(-50%,50%); }}
  .timeline-chart .reference-point {{ color:#566174; border-radius:0; }}
  .timeline-chart .phase-line {{ top:0; bottom:0; height:auto; width:0; border-left:1px dashed #777; border-radius:0; transform:none; }}
  .timeline-chart .drop-line {{ border-left:2px solid #a32d2d; }}
  @media (max-width:540px) {{ .timeline-charts {{ grid-template-columns:1fr; }} }}
  footer {{ margin-top:36px; color:#9a988f; font-size:11px; }}
</style></head><body>

<h1>Performance Test Report</h1>
<div class="meta">{metadata}</div>
<div class="meta">Target: {esc(target)} &nbsp;|&nbsp; Tool: {esc(tool)} &nbsp;|&nbsp; Generated: {now}
{f'&nbsp;|&nbsp; Plan: {esc(plan_id[:8])}' if plan_id else ''}</div>

{_release_section(release_readiness)}
<p>k6 thresholds {_badge(verdict.get('overall_passed'))}</p>
{f'<div class="headline">{esc(narrative.headline)}</div>' if not release_explanation else ""}

<p>{threshold_note}</p>{partial_note}
<h2>What happened</h2>
<p>{esc(report_summary)}</p>
{f'<p><a href="#run-timeline">{esc(drop_note)}</a></p>' if drop_note else ''}

<h2>Key metrics</h2>
<div class="grid">
  <div class="kpi"><div class="v">{cell(snapshot.get('requests'))}</div><div class="l">Requests</div></div>
  <div class="kpi"><div class="v">{throughput}</div><div class="l">Requests/sec</div></div>
  <div class="kpi"><div class="v">{rate(snapshot.get('error_rate'))}</div><div class="l">Error rate</div></div>
  <div class="kpi"><div class="v">{latency(lat.get('p95_ms'))}</div><div class="l">p95 latency</div></div>
  <div class="kpi"><div class="v">{latency(lat.get('p99_ms'))}</div><div class="l">p99 latency</div></div>
  <div class="kpi"><div class="v">{latency(lat.get('max_ms'))}</div><div class="l">max latency</div></div>
</div>

<h2>Threshold results</h2>
<table><thead><tr><th>Metric</th><th>Target</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>{checks_rows or '<tr><td colspan="4">No thresholds were defined.</td></tr>'}</tbody></table>

<h2>Workload and latency</h2>
{rate_note}
{f"<p>Planned executor {cell(execution['executor'])}</p>" if execution.get('executor') and execution.get('generated') and not execution.get('script_edited') else ''}
<p>Observed peak VUs {cell(snapshot.get('observed_peak_vus'))} · Iterations {cell(snapshot.get('iterations'))}
{f" completed / {cell(execution['planned_iterations'])} planned" if execution.get('planned_iterations') is not None and not execution.get('script_edited') else ''}
· Dropped iterations {cell(snapshot.get('dropped_iterations'))}</p>
<p>Bytes sent {cell(snapshot.get('bytes_sent'))} · Bytes received {cell(snapshot.get('bytes_received'))}</p>
<p>Average {latency(lat.get('avg_ms'))} · p50 {latency(lat.get('p50_ms'))} · p90 {latency(lat.get('p90_ms'))}</p>

<h2 id="run-timeline">Run timeline</h2>
<p>Values summarize traffic observed up to each sample.</p>
{f'<p>Planned phases · {phase_note}</p>' if phase_note else ''}
{f'<p>{esc(drop_note)} The solid red line marks this sample.</p>' if dropped else ''}
{timeline_charts}
<table><thead><tr><th>Elapsed (s)</th><th>Requests/s</th><th>p95 (ms)</th><th>Errors (%)</th><th>Dropped iterations (cumulative)</th></tr></thead>
<tbody>{sample_rows or '<tr><td colspan="5">Timeline samples are unavailable for this run.</td></tr>'}</tbody></table>

<h2>Per-endpoint</h2>
<table><thead><tr><th>Endpoint</th><th>Requests</th><th>HTTP failures</th><th>Avg</th><th>p95</th><th>Failed response checks</th><th>Status counts</th></tr></thead>
<tbody>{ep_rows or '<tr><td colspan="7">No per-endpoint data was recorded.</td></tr>'}</tbody></table>

<h2>Journeys</h2>
<table><thead><tr><th>Journey</th><th>Requests</th><th>HTTP failures</th><th>Iterations</th><th>Dropped</th><th>Failed checks</th></tr></thead>
<tbody>{journey_rows or '<tr><td colspan="6">No journey data was recorded.</td></tr>'}</tbody></table>

<h2>Response checks</h2>
<table><thead><tr><th>Check</th><th>Passed</th><th>Failed</th></tr></thead>
<tbody>{response_checks or '<tr><td colspan="3">No response checks were recorded.</td></tr>'}</tbody></table>

{service_section}
<h2>HTTP timing phases</h2>
<table><thead><tr><th>Endpoint</th><th>Phase</th><th>Avg (ms)</th><th>p95 (ms)</th></tr></thead>
<tbody>{timing_rows or '<tr><td colspan="4">No timing phases were recorded.</td></tr>'}</tbody></table>

<h2>Run observations</h2>
<ul>{obs or '<li>None.</li>'}</ul>
{recs_block}

<footer>Generated by AI Performance Testing Agent. Metrics and pass/fail are computed
deterministically; the written summary is AI-generated from those figures.</footer>
</body></html>"""
