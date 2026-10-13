"""Deterministic k6 renderer: LoadModel -> runnable k6 script.

k6 is the primary tool. No LLM - pure templating plus arithmetic to turn the load
profile into k6 ramping-vus stages and the thresholds into k6 threshold expressions.

Supports:
  - data-file parameterization (${field} -> row.field + SharedArray loader)
  - custom global headers (applied to every request)
"""

from __future__ import annotations

import json
import re

from jinja2 import Environment, PackageLoader, StrictUndefined

from perfagent.contracts.load_model import LoadModel
from perfagent.generator.k6_data import (
    body_to_k6_expr,
    k6_data_loader,
    k6_row_pick,
    path_to_k6_template,
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


def _scale_stages(model: LoadModel, scenario_weight_fraction: float) -> list[dict]:
    """Per-scenario stages: total VUs split across scenarios by weight.

    Uses largest-remainder so the per-scenario VUs sum to exactly the target, and a
    scenario with any share always gets at least 1 (k6 rejects all-zero scenarios).
    """
    stages = []
    for stage in model.load_profile.stages:
        if stage.target_users <= 0:
            target = 0
        else:
            raw = stage.target_users * scenario_weight_fraction
            target = max(1, round(raw))
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


def _prepare_scenarios(model: LoadModel, data_on: bool) -> list[dict]:
    fractions = model.normalised_weights()
    scenarios = []
    for i, (sc, frac) in enumerate(zip(model.scenarios, fractions, strict=False)):
        steps = []
        for st in sc.steps:
            has_ph = "${" in st.path or (st.body and "${" in json.dumps(st.body))
            if data_on:
                path_expr = path_to_k6_template(st.path)
                body_expr = body_to_k6_expr(st.body)
            else:
                path_expr = st.path
                body_expr = None
            steps.append(
                {
                    "name": st.name,
                    "method": st.method.value,
                    "method_lower": st.method.value.lower(),
                    "path": st.path,
                    "path_expr": path_expr,
                    "body_literal": json.dumps(st.body or {}),
                    "body_expr": body_expr,
                    "parameterized": bool(has_ph),
                }
            )
        scenarios.append(
            {
                "key": _identifier(sc.name, f"scenario_{i}").lower(),
                "func_name": _func_name(sc.name, i),
                "name": sc.name,
                "steps": steps,
                "min_think": sc.think_time.min_seconds,
                "think_span": round(sc.think_time.max_seconds - sc.think_time.min_seconds, 3),
                "stages": _scale_stages(model, frac),
            }
        )
    return scenarios


def render_k6(model: LoadModel, filename: str = "loadtest.js") -> str:
    """Render a LoadModel to k6 script source (returns the file content)."""
    data_on = uses_data(model)
    headers = getattr(model, "headers", {}) or {}
    template = _env.get_template("k6.js.j2")
    return template.render(
        target_base_url=model.target_base_url,
        filename=filename,
        profile_type=model.load_profile.type.value,
        peak_users=model.load_profile.peak_users,
        total_seconds=model.load_profile.total_seconds,
        scenarios=_prepare_scenarios(model, data_on),
        thresholds=_thresholds(model),
        data_on=data_on,
        data_loader=k6_data_loader(model) if data_on else "",
        row_pick=k6_row_pick() if data_on else "",
        has_headers=bool(headers),
        headers_json=json.dumps(headers),
    )