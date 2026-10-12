"""Test-data loading — parse many formats into one normalized shape, and validate.

Real load tests feed a data file (users, product ids, search terms) so each virtual
user acts differently. This module accepts CSV, TSV, TXT, and JSON/JSONL, normalizes
them all to a list of rows (dicts with named fields), and validates the file so bad
data is caught before a run.

IMPORTANT (guardrail boundary): the *values* in a data file are treated as sensitive
and go only to the deterministic runner, never to the LLM. Only the *field names*
(the schema) are exposed to the planner so the AI can reference ${field} placeholders.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field


@dataclass
class DataSet:
    """Normalized test data: named fields + rows, plus any validation warnings."""

    fields: list[str]
    rows: list[dict]
    source_format: str
    warnings: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def schema(self) -> dict:
        """Safe-to-share description (field names + row count) — no values."""
        return {
            "fields": self.fields,
            "row_count": self.row_count,
            "source_format": self.source_format,
            "warnings": self.warnings,
        }


class DataValidationError(ValueError):
    """Raised when a data file cannot be used (empty, malformed, inconsistent)."""


def detect_format(filename: str, content: str) -> str:
    """Best-effort format detection from extension, then content shape."""
    name = filename.lower()
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".tsv"):
        return "tsv"
    if name.endswith(".jsonl") or name.endswith(".ndjson"):
        return "jsonl"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".txt"):
        return "txt"
    # content-based fallback
    stripped = content.lstrip()
    if stripped.startswith("[") or stripped.startswith("{"):
        return "json"
    first_line = content.splitlines()[0] if content.splitlines() else ""
    if "\t" in first_line:
        return "tsv"
    if "," in first_line:
        return "csv"
    return "txt"


def _parse_delimited(content: str, delimiter: str, fmt: str) -> DataSet:
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if reader.fieldnames is None:
        raise DataValidationError("file has no header row")
    fields = [f.strip() for f in reader.fieldnames]
    if not fields or any(f == "" for f in fields):
        raise DataValidationError("header row has empty column name(s)")
    rows = []
    warnings = []
    for i, raw in enumerate(reader, start=2):  # line 2 = first data row
        row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
        if all((v is None or v == "") for v in row.values()):
            warnings.append(f"row {i} is empty — skipped")
            continue
        # DictReader puts extra columns under None; flag ragged rows
        if None in raw and raw[None]:
            warnings.append(f"row {i} has more columns than the header")
        rows.append({k: row.get(k, "") for k in fields})
    if not rows:
        raise DataValidationError("no data rows found")
    return DataSet(fields=fields, rows=rows, source_format=fmt, warnings=warnings)


def _parse_json(content: str) -> DataSet:
    data = json.loads(content)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data:
        raise DataValidationError("JSON must be a non-empty array of objects")
    if not all(isinstance(r, dict) for r in data):
        raise DataValidationError("JSON array must contain objects")
    # union of keys, in first-seen order
    fields: list[str] = []
    for r in data:
        for k in r:
            if k not in fields:
                fields.append(k)
    rows = [{k: r.get(k, "") for k in fields} for r in data]
    return DataSet(fields=fields, rows=rows, source_format="json")


def _parse_jsonl(content: str) -> DataSet:
    rows_raw = []
    for i, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise DataValidationError(f"line {i} is not valid JSON: {e}") from e
        if not isinstance(obj, dict):
            raise DataValidationError(f"line {i} is not a JSON object")
        rows_raw.append(obj)
    if not rows_raw:
        raise DataValidationError("no JSON lines found")
    fields: list[str] = []
    for r in rows_raw:
        for k in r:
            if k not in fields:
                fields.append(k)
    rows = [{k: r.get(k, "") for k in fields} for r in rows_raw]
    return DataSet(fields=fields, rows=rows, source_format="jsonl")


def _parse_txt(content: str, field_name: str = "value") -> DataSet:
    """One value per line -> rows with a single named field."""
    rows = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            rows.append({field_name: line})
    if not rows:
        raise DataValidationError("text file has no non-empty lines")
    return DataSet(fields=[field_name], rows=rows, source_format="txt")


def load_data(filename: str, content: str, txt_field: str = "value") -> DataSet:
    """Parse + validate a data file of any supported format into normalized rows."""
    if not content.strip():
        raise DataValidationError("file is empty")
    fmt = detect_format(filename, content)
    if fmt == "csv":
        return _parse_delimited(content, ",", "csv")
    if fmt == "tsv":
        return _parse_delimited(content, "\t", "tsv")
    if fmt == "json":
        return _parse_json(content)
    if fmt == "jsonl":
        return _parse_jsonl(content)
    return _parse_txt(content, field_name=txt_field)


def validate_fields_referenced(dataset: DataSet, referenced: set[str]) -> list[str]:
    """Return referenced ${fields} that are NOT present in the data (usage errors)."""
    return sorted(r for r in referenced if r not in dataset.fields)