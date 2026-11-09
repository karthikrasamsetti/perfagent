"""Correlation helpers for the k6 renderer.

Decides which ${name} placeholders are captured variables (reference vars.name) vs
data-file columns (reference row.name), and emits the k6 capture code for extracts.
"""

from __future__ import annotations

import json
import re

from perfagent.generator.generators import generator_js, is_generator

_POSTMAN = re.compile(r"\{\{\s*([A-Za-z_$][A-Za-z0-9_$]*(?:\([^}]*\))?)\s*\}\}")
def _normalize_postman(text):
    """Convert Postman {{var}} / {{$randomX}} to our ${var} / ${randomX} syntax."""
    return _POSTMAN.sub(lambda m: "${" + m.group(1).lstrip("$") + "}", text)

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*(?:\([^}]*\))?)\}")


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


def _ref(name: str, cap: set[str], has_data: bool = True) -> str:
    """How a ${name} reference renders:
       - a generator (uuid, randomInt(...), ...) -> its JS expression
       - a captured correlation variable        -> vars.name
       - a data-file column (when a data file exists) -> row.name
       - otherwise (unknown ${name}, no data file) -> '' (safe; avoids a crash)
    """
    gen = generator_js(name) if is_generator(name) else None
    if gen is not None:
        return gen
    base = name.split("(")[0]  # strip any args for the var/column name
    if base in cap:
        return f"vars.{base}"
    if has_data:
        return f"row.{base}"
    # No data file and not a captured var or generator — a reference we can't resolve.
    # Emit an empty string rather than row.X (which would throw: row is undefined).
    return "''"


def path_expr(path: str, cap: set[str], has_data: bool = True) -> str:
    """Render a path with ${name} -> its JS expression for a template literal."""
    path = _normalize_postman(path)
    return _PLACEHOLDER.sub(lambda m: "${" + _ref(m.group(1), cap, has_data) + "}", path)


def body_expr(body: dict | None, cap: set[str], has_data: bool = True) -> str:
    """Render a body dict (with ${name}) into a JS expression string."""
    if not body:
        return "{}"
    raw = _normalize_postman(json.dumps(body))
    # "${name}" (a quoted placeholder alone) -> its JS expression (unquoted).
    #   name may be a column, a captured var, or a generator like randomInt(1,5).
    raw = re.sub(r'"\$\{([A-Za-z_][A-Za-z0-9_]*(?:\([^}]*\))?)\}"',
                 lambda m: _ref(m.group(1), cap, has_data), raw)
    # inline "...${name}..." within a longer string -> template literal
    def _inline(m: re.Match) -> str:
        inner = _PLACEHOLDER.sub(lambda mm: "${" + _ref(mm.group(1), cap, has_data) + "}", m.group(1))
        return "`" + inner + "`"
    raw = re.sub(r'"([^"]*\$\{[A-Za-z_][A-Za-z0-9_]*(?:\([^}]*\))?\}[^"]*)"', _inline, raw)
    return raw


def headers_expr(headers: dict, cap: set[str], has_data: bool = True) -> str:
    """Render global headers, substituting ${name} refs inside header VALUES."""
    # Build a JS object literal where values containing ${name} become template literals.
    parts = []
    for k, v in headers.items():
        if isinstance(v, str) and _PLACEHOLDER.search(v):
            tmpl = _PLACEHOLDER.sub(lambda m: "${" + _ref(m.group(1), cap, has_data) + "}", v)
            parts.append(f"{json.dumps(k)}: `{tmpl}`")
        else:
            parts.append(f"{json.dumps(k)}: {json.dumps(v)}")
    return "{ " + ", ".join(parts) + " }"


def _json_path_to_k6(path: str) -> str:
    """Convert a JSON path with array indices to k6's dotted form.

    k6's r.json() uses dot notation for arrays: data[0].id -> data.0.id
    """
    return path.replace("[", ".").replace("]", "")


def extract_code(step, indent: str = "      ") -> str:
    """Emit k6 capture lines for a step's extracts (reads from `res`).

    Supports four sources:
      - json   -> res.json('path')   (arrays: data[0].id -> data.0.id)
      - header -> res.headers['Header-Name']
      - cookie -> res.cookies['name'][0].value
      - regex  -> first capture group of a pattern matched against the body
    """
    lines = []
    for ex in getattr(step, "extract", []) or []:
        source = getattr(ex, "source", "json")
        if source == "header":
            expr = f"res.headers[{json.dumps(ex.path)}]"
        elif source == "cookie":
            expr = (
                f"(res.cookies[{json.dumps(ex.path)}] && res.cookies[{json.dumps(ex.path)}][0] "
                f"? res.cookies[{json.dumps(ex.path)}][0].value : '')"
            )
        elif source == "regex":
            # match the pattern against the body, take capture group 1
            pat = json.dumps(ex.path)
            lines.append(
                f"{indent}try {{ var _m_{ex.var} = (res.body || '').match(new RegExp({pat})); "
                f"vars.{ex.var} = _m_{ex.var} ? _m_{ex.var}[1] : ''; }} "
                f"catch (e) {{ vars.{ex.var} = ''; }}"
            )
            continue
        else:  # json (with array-index support)
            expr = f"res.json({json.dumps(_json_path_to_k6(ex.path))})"
        lines.append(
            f"{indent}try {{ vars.{ex.var} = {expr}; }} "
            f"catch (e) {{ vars.{ex.var} = ''; }}"
        )
    return "\n".join(lines)


def headers_dynamic(headers: dict) -> bool:
    """True if any header value contains a ${name} reference (needs per-request build)."""
    return any(isinstance(v, str) and _PLACEHOLDER.search(v) for v in headers.values())


def assertion_checks(step) -> str:
    """Emit k6 check() entries for a step's assertions. Returns the JS object body."""
    import json as _json
    parts = []
    for a in getattr(step, "assertions", []) or []:
        kind = a.kind; op = a.op; val = a.value; path = a.path
        if kind == "status":
            # numeric status comparison
            cmp = {"eq": "===", "ne": "!==", "gt": ">", "lt": "<"}.get(op, "===")
            label = f"status {op} {val}"
            parts.append(f"{_json.dumps(label)}: (r) => r.status {cmp} {int(val) if str(val).lstrip('-').isdigit() else 0}")
        elif kind == "json_path":
            getter = f"r.json({_json.dumps(path)})"
            label = f"{path} {op} {val}"
            if op == "contains":
                parts.append(f"{_json.dumps(label)}: (r) => {{ try {{ return String({getter}).includes({_json.dumps(val)}); }} catch(e) {{ return false; }} }}")
            elif op in ("gt", "lt"):
                cmp = ">" if op == "gt" else "<"
                parts.append(f"{_json.dumps(label)}: (r) => {{ try {{ return Number({getter}) {cmp} {_json.dumps_num(val) if False else _num(val)}; }} catch(e) {{ return false; }} }}")
            else:  # eq / ne
                cmp = "==" if op == "eq" else "!="
                parts.append(f"{_json.dumps(label)}: (r) => {{ try {{ return String({getter}) {cmp} {_json.dumps(val)}; }} catch(e) {{ return false; }} }}")
        elif kind == "body_contains":
            label = f"body contains {val}"
            parts.append(f"{_json.dumps(label)}: (r) => r.body && r.body.includes({_json.dumps(val)})")
    return ", ".join(parts)


def _num(v):
    try:
        f = float(v); return int(f) if f.is_integer() else f
    except (ValueError, TypeError):
        return 0
