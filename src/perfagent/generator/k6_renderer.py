"""Deterministic k6 renderer: LoadModel -> runnable k6 script.

k6 is the primary tool. No LLM - pure templating plus arithmetic to turn the load
profile into k6 ramping-vus stages and the thresholds into k6 threshold expressions.
"""

from __future__ import annotations

import json
import re

from jinja2 import Environment, PackageLoader, StrictUndefined

from perfagent.contracts.load_model import LoadModel

_env = Environment(
    loader=PackageLoader("perfagent.generator", "templates"),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

# Map our threshold metric names to k6 metric expressions.
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

    k6 rejects a scenario whose stages are all zero, so whenever the source stage
    has any users we guarantee this scenario gets at least 1.
    """
    stages = []
    for stage in model.load_profile.stages:
        if stage.target_users <= 0:
            target = 0  # a genuine ramp-down-to-zero stays zero
        else:
            target = max(1, round(stage.target_users * scenario_weight_fraction))
        stages.append({"duration": stage.duration_seconds, "target": target})
    return stages


def _thresholds(model: LoadModel) -> list[dict]:
    out = []
    for th in model.thresholds:
        mapped = _METRIC_MAP.get(th.metric)
        if not mapped:
            continue
        metric, agg = mapped
        # error_rate is a fraction; latency metrics are ms. k6 expressions:
        #   'http_req_duration': ['p(95)<500']
        #   'errors': ['rate<0.01']
        out.append({"expr": f"'{metric}': ['{agg}{th.op}{th.value:g}'],"})
    return out


def _prepare_scenarios(model: LoadModel) -> list[dict]:
    fractions = model.normalised_weights()
    scenarios = []
    for i, (sc, frac) in enumerate(zip(model.scenarios, fractions, strict=False)):
        steps = []
        for st in sc.steps:
            steps.append(
                {
                    "name": st.name,
                    "method": st.method.value,
                    "method_lower": st.method.value.lower(),
                    "path": st.path,
                    "body_literal": json.dumps(st.body or {}),
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
    template = _env.get_template("k6.js.j2")
    return template.render(
        target_base_url=model.target_base_url,
        filename=filename,
        profile_type=model.load_profile.type.value,
        peak_users=model.load_profile.peak_users,
        total_seconds=model.load_profile.total_seconds,
        scenarios=_prepare_scenarios(model),
        thresholds=_thresholds(model),
    )