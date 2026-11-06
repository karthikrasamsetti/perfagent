"""Add dynamic data to a request body — the AI assigns generator tokens to the fields
that should vary per request, keeping fixed fields as-is.

Given a real JSON body (possibly deeply nested, like a shipping request), the AI
returns the SAME structure with generator tokens substituted where a field should be
unique/random:

    {"Contact": "John Smith"}   -> {"Contact": "${randomFullName}"}
    {"Email": "a@b.com"}        -> {"Email": "${randomEmail}"}
    {"Weight": 3120}            -> {"Weight": 3120}          (kept — a fixed spec value)

It only ever rewrites VALUES to generator tokens; it never changes keys or structure.
Runs through the guarded provider, so any secrets in the body are redacted first.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DynamizedBody(BaseModel):
    """The body with generator tokens assigned, plus a short note of what changed."""

    body: dict = Field(..., description="The same JSON body with generator tokens in "
                                        "fields that should vary per request.")
    changed_fields: list[str] = Field(
        default_factory=list,
        description="Dotted names of fields that were made dynamic, e.g. "
                    "'DeliverTo.Email', 'Pieces[0].Reference'.")
    notes: str = Field(default="", description="One short line on what was assigned.")


DYNAMIZE_SYSTEM_PROMPT = """\
You add dynamic test data to a JSON request body for load testing. You are given a \
JSON object. Return the SAME object with the SAME keys and structure, but replace the \
VALUES of fields that should be unique or random per request with a generator token. \
Keep fixed/spec values (weights, dimensions, country codes, service codes, fixed \
addresses the user clearly wants constant) unchanged.

DATA-FILE COLUMNS (real existing values) — IMPORTANT:
If the user has uploaded a data file, its column names are listed below. For a field that should use a REAL existing value the system expects (e.g. a real customer branch, account number, product id, username that must already exist), use ${columnName} for a matching column INSTEAD of a random generator. Random values would fail validation against a real API; data-file columns are real. Prefer a data-file column when a field clearly corresponds to one; otherwise use a generator or keep it fixed.

Generator tokens to use (choose the best fit per field):
  ${uuid}                 - a unique id / order number / reference
  ${randomEmail}          - an email field
  ${randomFullName}       - a person/contact name
  ${randomFirstName} / ${randomLastName}
  ${randomCompanyName}    - a company/organization name
  ${randomStreetAddress}  - a street address line
  ${randomCity}           - a city
  ${randomState}          - a state/province code
  ${randomZipCode}        - a postal/zip code
  ${randomPhone}          - a phone number
  ${randomCatchPhrase}    - free-text notes / descriptions / special instructions
  ${randomBic}            - a bank/BIC-like alphanumeric code or reference
  ${randomInt(min,max)}   - a numeric field that should vary in a range
  ${randomString(n)}      - a generic random string
  ${timestamp}            - a current timestamp
  ${dateOffset(n,'days')} - a date N days from now (e.g. expiration, departure)

Guidance:
- Names, emails, companies, phones, free-text notes, references, order numbers, and \
dates are usually good to make dynamic.
- Physical specs (weight, width, length, height, units of measurement), country/ISO \
codes, service codes, and enum-like attribute lists are usually FIXED — keep them.
- For an obviously fixed street address block the user hard-coded, you may keep it, \
but contact/company/phone/notes within it can still be dynamic.
- NEVER invent new keys or remove keys. NEVER change the structure. Only rewrite values.
- If a value is already a generator token or a ${...}/{{...}} placeholder, keep it.

Return the full body with tokens applied, the list of changed field paths, and a one-\
line note."""


def build_dynamize_user_prompt(body_json: str, columns: list[str] | None = None) -> str:
    cols = ""
    if columns:
        cols = ("\n\nAvailable data-file columns (use ${name} for a field that should "
                "take a real existing value from one of these):\n  "
                + ", ".join(columns))
    return (
        "Here is the request body. Add dynamic generator tokens to the fields that "
        "should vary per request, use a data-file column where a field should take a "
        "real existing value, keep fixed spec values unchanged, and return the full "
        "body unchanged in structure:\n\n" + body_json + cols
    )
