"""Correlation helpers for the k6 renderer.

Decides which ${name} placeholders are captured variables (reference vars.name) vs
data-file columns (reference row.name), and emits the k6 capture code for extracts.
"""

from __future__ import annotations

import json
import re

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def captured_vars(model) -> set[str]:
    """All variable names captured by any step's extract across the model."""
    out: set[str] = set()
    for sc in model.scenarios:
        for st in sc.steps:
            for ex in getattr(st, "extract", []) or []:
                out.add(ex.var)
    return out


def uses_correlation(model) -> bool:
    return bool(captured_vars(model))


def _ref(name: str, cap: set[str]) -> str:
    """How a ${name} reference renders: vars.name if captured, else row.name (data)."""
    return f"vars.{name}" if name in cap else f"row.{name}"


def path_expr(path: str, cap: set[str]) -> str:
    """Render a path with ${name} -> ${vars.name} / ${row.name} for a template literal."""
    return _PLACEHOLDER.sub(lambda m: "${" + _ref(m.group(1), cap) + "}", path)


def body_expr(body: dict | None, cap: set[str]) -> str:
    """Render a body dict (with ${name}) into a JS expression string."""
    if not body:
        return "{}"
    raw = json.dumps(body)
    # "${name}" (a quoted placeholder alone) -> vars.name / row.name (unquoted)
    raw = re.sub(r'"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"',
                 lambda m: _ref(m.group(1), cap), raw)
    # inline "...${name}..." within a longer string -> template literal
    def _inline(m: re.Match) -> str:
        inner = _PLACEHOLDER.sub(lambda mm: "${" + _ref(mm.group(1), cap) + "}", m.group(1))
        return "`" + inner + "`"
    raw = re.sub(r'"([^"]*\$\{[A-Za-z_][A-Za-z0-9_]*\}[^"]*)"', _inline, raw)
    return raw


def headers_expr(headers: dict, cap: set[str]) -> str:
    """Render global headers, substituting ${name} refs inside header VALUES."""
    # Build a JS object literal where values containing ${name} become template literals.
    parts = []
    for k, v in headers.items():
        if isinstance(v, str) and _PLACEHOLDER.search(v):
            tmpl = _PLACEHOLDER.sub(lambda m: "${" + _ref(m.group(1), cap) + "}", v)
            parts.append(f"{json.dumps(k)}: `{tmpl}`")
        else:
            parts.append(f"{json.dumps(k)}: {json.dumps(v)}")
    return "{ " + ", ".join(parts) + " }"


def extract_code(step, indent: str = "      ") -> str:
    """Emit k6 capture lines for a step's extracts (reads from `res`)."""
    lines = []
    for ex in getattr(step, "extract", []) or []:
        # json field path: token  -> res.json('token'); data.id -> res.json('data.id')
        lines.append(
            f"{indent}try {{ vars.{ex.var} = res.json({json.dumps(ex.path)}); }} "
            f"catch (e) {{ vars.{ex.var} = ''; }}"
        )
    return "\n".join(lines)


def headers_dynamic(headers: dict) -> bool:
    """True if any header value contains a ${name} reference (needs per-request build)."""
    return any(isinstance(v, str) and _PLACEHOLDER.search(v) for v in headers.values())
