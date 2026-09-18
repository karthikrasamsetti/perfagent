"""Generator stage: render a LoadModel to a runnable script for a chosen tool.

Adding a new tool = adding one renderer here and one entry in _RENDERERS. Nothing
else in the pipeline changes - this is the "one plan, any tool" seam.

k6 is the primary/default tool. Locust is available as an alternative.
"""

from __future__ import annotations

from collections.abc import Callable

from perfagent.contracts.artifacts import PlanArtifact, ScriptArtifact
from perfagent.contracts.load_model import LoadModel
from perfagent.generator.k6_renderer import render_k6
from perfagent.generator.locust_renderer import render_locust

# tool -> (default filename, render function)
_RENDERERS: dict[str, tuple[str, Callable[[LoadModel, str], str]]] = {
    "k6": ("loadtest.js", render_k6),
    "locust": ("locustfile.py", render_locust),
}

DEFAULT_TOOL = "k6"


def supported_tools() -> list[str]:
    # k6 first (primary), then the rest.
    return ["k6"] + sorted(t for t in _RENDERERS if t != "k6")


def render(model: LoadModel, tool: str = DEFAULT_TOOL) -> tuple[str, str]:
    """Render a LoadModel for `tool`. Returns (filename, content)."""
    key = tool.lower()
    if key not in _RENDERERS:
        raise ValueError(
            f"unsupported tool {tool!r}; supported: {', '.join(supported_tools())}"
        )
    filename, fn = _RENDERERS[key]
    content = fn(model, filename)
    return filename, content


def generate_script(plan: PlanArtifact, tool: str = DEFAULT_TOOL) -> ScriptArtifact:
    """Render from a PlanArtifact, preserving lineage back to the plan."""
    filename, content = render(plan.load_model, tool)
    return ScriptArtifact(
        plan_id=plan.id,
        tool=tool.lower(),
        filename=filename,
        content=content,
    )


__all__ = ["render", "generate_script", "supported_tools", "DEFAULT_TOOL"]
