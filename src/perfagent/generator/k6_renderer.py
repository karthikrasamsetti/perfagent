"""Deterministic k6 renderer: LoadModel -> runnable k6 script.

k6 is the primary tool. No LLM. Supports:
  - data-file parameterization (${field} -> row.field + SharedArray)
  - global headers (static or with ${var} references)
  - correlation: a step can extract a value from its response into vars.X, and later
    steps reference it as ${X}

The per-step request JS is generated in Python (not Jinja) because correlation needs
sequential logic (capture into vars, reuse later) that's clearer in code.
"""

from __future__ import annotations

import json
import re

from jinja2 import Environment, PackageLoader, StrictUndefined

from perfagent.contracts.load_model import LoadModel
from perfagent.generator.k6_corr import (
    assertion_checks,
    body_expr,
    captured_vars,
    extract_code,
    headers_dynamic,
    headers_expr,
    path_expr,
    uses_correlation,
)
from perfagent.generator.generators import FAKER_HELPERS, UUID_IMPORT, needs_faker, needs_uuid_import
from perfagent.generator.k6_data import (
    EXEC_IMPORT,
    k6_data_loader,
    k6_row_pick,
    needs_exec_import,
    uses_data,
)

_env = Environment(
    loader=PackageLoader("perfagent.generator", "templates"),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

_METRIC_MAP = {
    "p95_ms": ("http_req_duration", "p(95)"),
    "p99_ms": ("http_req_duration", "p(99)"),
    "p50_ms": ("http_req_duration", "p(50)"),
    "median_ms": ("http_req_duration", "med"),
    "avg_ms": ("http_req_duration", "avg"),
    "error_rate": ("errors", "rate"),
}


def _identifier(text: str, fallback: str) -> str:
    cleaned = re.sub(r"\W+", "_", text.strip()).strip("_")
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def _func_name(name: str, index: int) -> str:
    ident = _identifier(name, f"scenario_{index}")
    parts = ident.split("_")
    camel = parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
    return camel or f"scenario{index}"


def _scale_stages(model: LoadModel, frac: float) -> list[dict]:
    stages = []
    for stage in model.load_profile.stages:
        target = 0 if stage.target_users <= 0 else max(1, round(stage.target_users * frac))
        stages.append({"duration": stage.duration_seconds, "target": target})
    return stages


def _thresholds(model: LoadModel) -> list[dict]:
    out = []
    for th in model.thresholds:
        mapped = _METRIC_MAP.get(th.metric)
        if not mapped:
            continue
        metric, agg = mapped
        out.append({"expr": f"'{metric}': ['{agg}{th.op}{th.value:g}'],"})
    return out


def _step_js(step, cap, dynamic, has_headers, has_data, static_headers_ref="HEADERS") -> str:
    """Generate the k6 request block for one step (handles vars, row, extract, headers)."""
    name = step.name
    method = step.method.value
    ml = method.lower()
    p = path_expr(step.path, cap, has_data)
    url = f"`${{BASE_URL}}{p}`"

    # headers param
    if has_headers and dynamic:
        hdr = "DYN_HEADERS(vars, typeof row !== 'undefined' ? row : {})"
    elif has_headers:
        hdr = static_headers_ref
    else:
        hdr = None

    tags = f"tags: {{ name: {json.dumps(name)} }}"
    capture = extract_code(step, indent="      ")

    lines = ["    {"]
    if method in ("GET", "DELETE"):
        params_obj = "{ " + (f"headers: {hdr}, " if hdr else "") + tags + " }"
        if method == "GET":
            lines.append(f"      const res = http.get({url}, {params_obj});")
        else:
            lines.append(f"      const res = http.del({url}, null, {params_obj});")
    else:
        gql = getattr(step, "graphql_query", "") or ""
        if gql:
            # GraphQL: body is {query, variables} — variables come from step.body
            vars_expr = body_expr(step.body, cap, has_data) if step.body else "{}"
            lines.append(
                f"      const payload = JSON.stringify({{ query: {json.dumps(gql)}, "
                f"variables: {vars_expr} }});")
        else:
            be = body_expr(step.body, cap, has_data)
            lines.append(f"      const payload = JSON.stringify({be});")
        base_hdr = "{ 'Content-Type': 'application/json' }"
        merged = base_hdr if not hdr else f"Object.assign({base_hdr}, {hdr})"
        lines.append(f"      const params = {{ headers: {merged}, {tags} }};")
        lines.append(f"      const res = http.{ml}({url}, payload, params);")

    base_check = f"{json.dumps(name + ' status ok')}: (r) => r.status >= 200 && r.status < 400"
    extra = assertion_checks(step)
    all_checks = base_check + (", " + extra if extra else "")
    lines.append(f"      const ok = check(res, {{ {all_checks} }});")
    lines.append("      errorRate.add(res.status >= 400 || !ok);")
    # Console logging on failure — so live logs explain WHY a request failed
    # (which step, status, and a short body preview). Mirrors how engineers log.
    sname = json.dumps(step.name)
    lines.append(
        "      if (res.status >= 400 || !ok) {\n"
        f"        console.error(`[FAIL][VU ${{__VU}}] {step.name} — status ${{res.status}}` + "
        "(res.body ? ` — body: ${String(res.body).replace(/\\s+/g,' ').slice(0,180)}` : ''));\n"
        "      }")
    if capture:
        lines.append(capture)
    lines.append("    }")
    return "\n".join(lines)


def _scenario_js(sc, si, cap, data_on, corr_on, has_headers, dynamic,
                 row_mode="random", scenario_count=1) -> str:
    fn = _func_name(sc.name, si)
    out = [f"export function {fn}() {{"]
    if corr_on:
        out.append("  let vars = {};")
    if data_on:
        out.append(k6_row_pick(row_mode, si, scenario_count))
    out.append(f"  group({json.dumps(sc.name)}, function () {{")
    think = round(sc.think_time.max_seconds - sc.think_time.min_seconds, 3)
    lo = sc.think_time.min_seconds
    for step in sc.steps:
        out.append(_step_js(step, cap, dynamic, has_headers, data_on))
        out.append(f"    sleep(Math.random() * {think} + {lo});")
    out.append("  });")
    out.append("}")
    return "\n".join(out)


def render_k6(model: LoadModel, filename: str = "loadtest.js") -> str:
    data_on = uses_data(model)
    corr_on = uses_correlation(model)
    cap = captured_vars(model)
    headers = getattr(model, "headers", {}) or {}
    has_headers = bool(headers)
    dynamic = has_headers and headers_dynamic(headers)

    fractions = model.normalised_weights()
    scenarios_meta = []
    scenario_funcs = []
    for i, (sc, frac) in enumerate(zip(model.scenarios, fractions, strict=False)):
        scenarios_meta.append({
            "key": _identifier(sc.name, f"scenario_{i}").lower(),
            "func_name": _func_name(sc.name, i),
            "stages": _scale_stages(model, frac),
        })
        scenario_funcs.append(_scenario_js(
            sc, i, cap, data_on, corr_on, has_headers, dynamic,
            row_mode=model.data_file.row_mode if data_on else "random",
            scenario_count=len(model.scenarios)))

    # extra imports (uuid generator) + headers declarations.
    # Build as a list and join, so the uuid import is never overwritten by the
    # header declaration (that was a bug: a reassignment wiped the import).
    decl_parts = []
    if needs_exec_import(model):
        decl_parts.append(EXEC_IMPORT)
    if needs_uuid_import(model):
        decl_parts.append(UUID_IMPORT)
    if needs_faker(model):
        decl_parts.append(FAKER_HELPERS)
    if has_headers and dynamic:
        # DYN_HEADERS builds headers per request, substituting ${var}/${row} refs
        decl_parts.append(
            "function DYN_HEADERS(vars, row) {\n  return " + headers_expr(headers, cap, data_on) + ";\n}"
        )
    elif has_headers:
        decl_parts.append("const HEADERS = " + json.dumps(headers) + ";")
    header_decls = ("\n".join(decl_parts) + "\n") if decl_parts else ""

    template = _env.get_template("k6.js.j2")
    return template.render(
        target_base_url=model.target_base_url,
        filename=filename,
        profile_type=model.load_profile.type.value,
        peak_users=model.load_profile.peak_users,
        total_seconds=model.load_profile.total_seconds,
        scenarios=scenarios_meta,
        thresholds=_thresholds(model),
        data_on=data_on,
        data_loader=k6_data_loader(model) if data_on else "",
        header_decls=header_decls,
        scenario_funcs="\n\n".join(scenario_funcs),
        insecure_tls=getattr(model, "insecure_tls", False),
    )
