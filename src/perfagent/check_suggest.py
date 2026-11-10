"""Generate validation checks from a sample API response (Option B — paste a response).

A performance engineer runs the request manually, looks at the real response, then writes
robust validation. This mirrors that: the user pastes a real response (XML or JSON), the
AI proposes assertions (fields that should exist, errors that should NOT appear, numeric
fields that should be positive). The user reviews and keeps the ones they want.

SAFETY: the pasted response goes through the guarded provider, so values that look like
secrets/PII are redacted before the AI sees them. The AI only needs the STRUCTURE
(element/field names) to propose checks, not the real values. This is the always-safe
input mode (vs. a live fetch, which is gated on in-tenant AI — see the design note).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SuggestedCheck(BaseModel):
    kind: str = Field(..., description="status | json_path | body_contains | not_contains | response_time")
    op: str = Field(default="eq", description="eq | ne | contains | gt | lt")
    path: str = Field(default="", description="For json_path: the field path.")
    value: str = Field(default="", description="Expected value / text / number.")
    reason: str = Field(default="", description="One short line: why this check.")


class SuggestedChecks(BaseModel):
    checks: list[SuggestedCheck] = Field(default_factory=list)
    notes: str = Field(default="", description="One line on what was analyzed.")


CHECK_SUGGEST_SYSTEM_PROMPT = """\
You help a performance engineer write robust response validation. You are given a SAMPLE \
response from an API (XML or JSON). Propose a set of assertions that validate a GOOD \
response and catch a BAD one. Use these check kinds:
  body_contains  — an element/field that should be present (e.g. "<Rate>", "orderId")
  not_contains   — text that signals an error and must NOT appear (e.g. "<Error>", "Invalid")
  json_path      — a JSON field with an expected value or comparison (eq/ne/gt/lt)
  status         — the expected HTTP status (usually 200)
  response_time  — a reasonable max latency in ms (only if clearly useful)

Guidance:
- For XML, prefer body_contains on the key elements (e.g. the schema's important tags) and \
not_contains on error markers you can infer (e.g. "<Error>", "Invalid", "Not Found").
- For JSON, prefer json_path checks on the key fields; use gt for amounts that should be \
positive (e.g. a total/price > 0).
- Propose the checks that matter (the important schema elements and the error guards), not \
one for every field. Aim for a tight, meaningful set.
- Base checks on the STRUCTURE you see. Do not assume fields that aren't in the sample.
- Give each check a one-line reason.

Return only the structured list of checks."""


def build_check_suggest_prompt(sample_response: str) -> str:
    snippet = sample_response[:6000]
    return (
        "Here is a sample API response. Propose validation checks (present elements, "
        "error guards, positive amounts) that a load test should assert:\n\n" + snippet
    )
