"""Helpers for data-parameterized k6 scripts.

Turns ${field} placeholders in paths and bodies into k6 per-iteration references,
and builds the k6 SharedArray loader that reads the data file so each virtual user
picks a row. Pure string work — no LLM.
"""

from __future__ import annotations

import json
import re

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def referenced_fields(model) -> set[str]:
    """All ${field} names referenced anywhere in the model's steps."""
    found: set[str] = set()
    for sc in model.scenarios:
        for st in sc.steps:
            found.update(_PLACEHOLDER.findall(st.path))
            if st.body:
                found.update(_PLACEHOLDER.findall(json.dumps(st.body)))
    return found


def path_to_k6_template(path: str) -> str:
    """`/product/${product_id}` -> JS template literal body `/product/${row.product_id}`.

    (k6 uses `row` as the per-iteration record; see the loader below.)
    """
    return _PLACEHOLDER.sub(lambda m: "${row." + m.group(1) + "}", path)


def body_to_k6_expr(body: dict | None) -> str:
    """Turn a body dict (possibly with ${field}) into a JS expression string.

    Produces valid JS where ${field} becomes row.field, e.g.
      {"username": "${username}", "n": 5}  ->  {"username": row.username, "n": 5}
    """
    if not body:
        return "{}"
    raw = json.dumps(body)
    # Replace ""${field}"" (a quoted placeholder) with row.field (unquoted JS ref).
    raw = re.sub(r'"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"', r"row.\1", raw)
    # Replace any remaining inline ${field} inside a longer string with a template.
    # e.g. "user-${id}" -> `user-${row.id}`
    def _inline(m: re.Match) -> str:
        inner = _PLACEHOLDER.sub(lambda mm: "${row." + mm.group(1) + "}", m.group(1))
        return "`" + inner + "`"
    raw = re.sub(r'"([^"]*\$\{[A-Za-z_][A-Za-z0-9_]*\}[^"]*)"', _inline, raw)
    return raw


def uses_data(model) -> bool:
    return getattr(model, "data_file", None) is not None and bool(referenced_fields(model))


def k6_data_loader(model) -> str:
    """The k6 SharedArray + per-iteration row picker, or '' if no data file."""
    if not uses_data(model):
        return ""
    df = model.data_file
    fmt = df.source_format
    fname = df.filename
    if fmt in ("csv", "tsv"):
        delim = "\\t" if fmt == "tsv" else ","
        return (
            "import { SharedArray } from 'k6/data';\n"
            "import papaparse from 'https://jslib.k6.io/papaparse/5.1.1/index.js';\n\n"
            f"const DATA = new SharedArray('data', function () {{\n"
            f"  return papaparse.parse(open('./{fname}'), "
            f"{{ header: true, delimiter: '{delim}', skipEmptyLines: true }}).data;\n"
            "});\n"
        )
    if fmt == "txt":
        # one value per line -> rows of {value: ...}
        return (
            "import { SharedArray } from 'k6/data';\n\n"
            f"const DATA = new SharedArray('data', function () {{\n"
            f"  return open('./{fname}').split('\\n').map(function (l) {{ return l.trim(); }})\n"
            "    .filter(function (l) { return l.length > 0; })\n"
            "    .map(function (v) { return { value: v }; });\n"
            "});\n"
        )
    # json / jsonl
    if fmt == "jsonl":
        return (
            "import { SharedArray } from 'k6/data';\n\n"
            f"const DATA = new SharedArray('data', function () {{\n"
            f"  return open('./{fname}').split('\\n').filter(function (l) {{ return l.trim(); }})\n"
            "    .map(function (l) { return JSON.parse(l); });\n"
            "});\n"
        )
    return (
        "import { SharedArray } from 'k6/data';\n\n"
        f"const DATA = new SharedArray('data', function () {{\n"
        f"  return JSON.parse(open('./{fname}'));\n"
        "});\n"
    )


def k6_row_pick() -> str:
    """JS line that picks a per-iteration row (random, so VUs vary)."""
    return "  const row = DATA[Math.floor(Math.random() * DATA.length)];"