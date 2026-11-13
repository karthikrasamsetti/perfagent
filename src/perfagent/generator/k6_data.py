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


def k6_row_pick(row_mode: str = "random", scenario_index: int = 0,
                scenario_count: int = 1) -> str:
    """JS that picks the data row for one iteration of a journey.

      random      any row — rows can repeat (the long-standing default).
      sequential  rows in file order, shared by all virtual users of the journey,
                  starting again at the top when the file runs out.
      unique      every row is used at most once in the whole test. Journeys take
                  interleaved rows (journey 0: rows 0, n, 2n…; journey 1: rows 1,
                  n+1…) so two journeys never share a row. When the rows run out
                  the test is stopped with a clear message rather than reusing data.

    `exec.scenario.iterationInTest` is k6's counter of iterations of a scenario
    across ALL its virtual users, so no two iterations get the same number.
    """
    if row_mode == "sequential":
        return "  const row = DATA[exec.scenario.iterationInTest % DATA.length];"
    if row_mode == "unique":
        n, i = max(1, scenario_count), scenario_index
        return (
            f"  const _rowIndex = exec.scenario.iterationInTest * {n} + {i};\n"
            "  if (_rowIndex >= DATA.length) {\n"
            "    exec.test.abort('Data file exhausted: every one of its ' + DATA.length +\n"
            "      ' rows has been used once. Add rows, or let rows repeat.');\n"
            "  }\n"
            "  const row = DATA[_rowIndex];"
        )
    return "  const row = DATA[Math.floor(Math.random() * DATA.length)];"


def needs_exec_import(model) -> bool:
    """True when row selection needs k6's execution module."""
    return uses_data(model) and model.data_file.row_mode in ("sequential", "unique")


EXEC_IMPORT = "import exec from 'k6/execution';"
