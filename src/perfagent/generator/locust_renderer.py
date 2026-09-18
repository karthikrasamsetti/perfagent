"""Deterministic Locust renderer: LoadModel -> runnable Locust script.

No LLM. Same input always yields the same output. This is pure templating plus a
little arithmetic to turn the load profile into Locust LoadTestShape stages.
"""

from __future__ import annotations

import json
import math
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


def _identifier(text: str, fallback: str) -> str:
    """Turn an arbitrary label into a safe Python identifier."""
    cleaned = re.sub(r"\W+", "_", text.strip()).strip("_")
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def _class_name(name: str, index: int) -> str:
    ident = _identifier(name, f"scenario_{index}")
    return "".join(part.capitalize() for part in ident.split("_")) or f"Scenario{index}"


def _prepare_scenarios(model: LoadModel) -> list[dict]:
    scenarios = []
    for i, sc in enumerate(model.scenarios):
        steps = []
        for j, st in enumerate(sc.steps):
            steps.append(
                {
                    "func_name": _identifier(st.name, f"step_{j}"),
                    "name": st.name,
                    "method": st.method.value,
                    "method_lower": st.method.value.lower(),
                    "path": st.path,
                    "body_literal": json.dumps(st.body or {}),
                }
            )
        scenarios.append(
            {
                "class_name": _class_name(sc.name, i),
                "name": sc.name,
                "weight": sc.weight,
                # Locust weights are integers; scale relative weights to whole numbers.
                "weight_int": max(1, round(sc.weight * 10)),
                "min_think": sc.think_time.min_seconds,
                "max_think": sc.think_time.max_seconds,
                "steps": steps,
            }
        )
    return scenarios


def _shape_stages(model: LoadModel) -> list[dict]:
    """Convert absolute-duration stages into cumulative-time Locust shape entries."""
    stages = []
    cumulative = 0
    prev_users = 0
    for stage in model.load_profile.stages:
        cumulative += stage.duration_seconds
        # Spawn rate: reach the target change over this stage, at least 1/sec.
        delta = abs(stage.target_users - prev_users)
        spawn_rate = max(1, math.ceil(delta / max(1, stage.duration_seconds)))
        stages.append(
            {
                "cumulative": cumulative,
                "users": stage.target_users,
                "spawn_rate": spawn_rate,
            }
        )
        prev_users = stage.target_users
    return stages


def render_locust(model: LoadModel, filename: str = "locustfile.py") -> str:
    """Render a LoadModel to Locust script source (returns the file content)."""
    template = _env.get_template("locust.py.j2")
    peak = model.load_profile.peak_users
    total = model.load_profile.total_seconds
    return template.render(
        target_base_url=model.target_base_url,
        filename=filename,
        profile_type=model.load_profile.type.value,
        peak_users=peak,
        total_seconds=total,
        spawn_rate=max(1, math.ceil(peak / max(1, total // 10 or 1))),
        scenarios=_prepare_scenarios(model),
        shape_stages=_shape_stages(model),
    )
