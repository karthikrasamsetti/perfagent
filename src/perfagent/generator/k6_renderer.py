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
    "p90_ms": ("http_req_duration", "p(90)"),
    "max_ms": ("http_req_duration", "max"),
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


def _allocate_users(total: int, fractions: list[float]) -> list[int]:
    values = [int(total * fraction) for fraction in fractions]
    highest = max(range(len(fractions)), key=fractions.__getitem__)
    values[highest] += total - sum(values)
    # Keep every journey active when the requested total can accommodate it.
    if total >= len(values):
        for i, value in enumerate(values):
            if value == 0:
                donor = max(range(len(values)), key=values.__getitem__)
                values[donor] -= 1
                values[i] = 1
    return values


def _allocate(total: int, fractions: list[float]) -> list[int]:
    """Give every journey a slot, then distribute the rest by weight."""
    if total < len(fractions):
        raise ValueError("Iteration rate and preallocated users must each be at least the number of journeys.")
    remainder = total - len(fractions)
    values = [1 + int(remainder * fraction) for fraction in fractions]
    order = sorted(range(len(fractions)), key=lambda i:
                   remainder * fractions[i] - int(remainder * fractions[i]), reverse=True)
    for i in order[:total - sum(values)]:
        values[i] += 1
    return values


def _thresholds(model: LoadModel) -> list[dict]:
    rules: dict[str, list[str]] = {}
    for th in model.thresholds:
        mapped = _METRIC_MAP.get(th.metric)
        if not mapped:
            continue
        metric, agg = mapped
        rules.setdefault(metric, []).append(f"{agg}{th.op}{str(th.value).removesuffix('.0')}")
    if model.load_profile.target_request_rate is not None:
        expected = model.load_profile.target_request_rate * model.load_profile.total_seconds
        rules["http_reqs"] = [f"count>={expected}"]
        rules["dropped_iterations"] = ["count<1"]
    return [{"expr": f"'{metric}': {expressions!r},"} for metric, expressions in rules.items()]


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
    lines.append(f"      const ok = check(res, {{ {all_checks} }}, {{ perfagent_endpoint: {json.dumps(name)} }});")
    lines.append("      errorRate.add(res.status >= 400 || !ok);")
    # Response bodies may contain credentials or user data.
    sname = json.dumps(step.name)
    lines.append(
        "      if (res.status >= 400 || !ok) {\n"
        f"        console.error(`[FAIL][VU ${{__VU}}] ${{{sname}}} — status ${{res.status}}`);\n"
        "      }")
    if capture:
        lines.append(capture)
        for extract in step.extract:
            label = json.dumps(f"{step.name} captured {extract.var}")
            value = f"vars.{extract.var}"
            lines.append(
                f"      if (__ENV.PERFAGENT_VERIFY === '1') check({value}, "
                f"{{ {label}: (v) => v !== undefined && v !== null && v !== '' }});"
            )
    lines.append("    }")
    return "\n".join(lines)


def _scenario_js(sc, si, cap, data_on, corr_on, has_headers, dynamic,
                 row_mode="random", scenario_count=1, arrival=False) -> str:
    fn = _func_name(sc.name, si)
    out = [f"export function {fn}() {{"]
    if corr_on:
        out.append("  let vars = {};")
    if data_on:
        out.append(k6_row_pick(row_mode, si, scenario_count))
    out.append(f"  group({json.dumps(sc.name)}, function () {{")
    think = round(sc.think_time.max_seconds - sc.think_time.min_seconds, 3)
    lo = sc.think_time.min_seconds
    for index, step in enumerate(sc.steps):
        out.append(_step_js(step, cap, dynamic, has_headers, data_on))
        if not arrival or index < len(sc.steps) - 1:
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

    request_rate = model.load_profile.target_request_rate
    if request_rate is not None and (
        len(model.scenarios) != 1 or len(model.scenarios[0].steps) != 1
        or model.load_profile.arrival_rate != request_rate
    ):
        raise ValueError("An HTTP request-rate target needs one journey with one request and a matching arrival rate.")

    fractions = model.normalised_weights()
    rates = _allocate(model.load_profile.arrival_rate, fractions) if model.load_profile.arrival_rate else [0] * len(fractions)
    vus = _allocate(model.load_profile.pre_allocated_vus, fractions) if model.load_profile.arrival_rate else [0] * len(fractions)
    scenarios_meta = []
    scenario_funcs = []
    profile = model.load_profile
    if not profile.arrival_rate and max(profile.peak_users, profile.start_users) < len(fractions):
        raise ValueError("Peak users must be at least the number of journeys. Increase users or combine journeys.")
    targets = [_allocate_users(stage.target_users, fractions) for stage in profile.stages]
    starts = _allocate_users(profile.start_users, fractions)
    for i, sc in enumerate(model.scenarios):
        scenarios_meta.append({
            "key": _identifier(sc.name, f"scenario_{i}").lower(),
            "func_name": _func_name(sc.name, i),
            "stages": [{"duration": stage.duration_seconds, "target": allocation[i]}
                       for stage, allocation in zip(profile.stages, targets, strict=True)],
            "rate": rates[i],
            "vus": vus[i],
            "start_vus": starts[i],
        })
        scenario_funcs.append(_scenario_js(
            sc, i, cap, data_on, corr_on, has_headers, dynamic,
            row_mode=model.data_file.row_mode if data_on else "random",
            scenario_count=len(model.scenarios), arrival=bool(model.load_profile.arrival_rate)))

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
        target_base_url=" ".join(model.target_base_url.splitlines()),
        target_js=json.dumps(model.target_base_url),
        filename=" ".join(filename.splitlines()),
        profile_type=model.load_profile.type.value,
        peak_users=model.load_profile.peak_users,
        total_seconds=model.load_profile.total_seconds,
        arrival_rate=model.load_profile.arrival_rate,
        request_rate=request_rate,
        graceful_stop_seconds=model.load_profile.graceful_stop_seconds,
        scenarios=scenarios_meta,
        thresholds=_thresholds(model),
        data_on=data_on,
        data_loader=k6_data_loader(model) if data_on else "",
        header_decls=header_decls,
        scenario_funcs="\n\n".join(scenario_funcs),
        insecure_tls=getattr(model, "insecure_tls", False),
    )
