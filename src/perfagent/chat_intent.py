"""Chat-to-plan — turn a free-text description (and/or a pasted Postman collection)
into a structured PlanRequest the planner can use.

The user types things like:
    "Load test the checkout flow with 100 users for 2 minutes. Make each signup
     email unique and use a random quantity 1-5."
or pastes a Postman collection and says "stress test these endpoints".

This module asks the LLM to extract the structured intent (target, endpoints with
bodies, user count, duration, test type, and which body fields should be dynamic
generators). The LLM only fills a validated schema — it never writes free code. The
result flows into the normal plan review, so the human still approves.

Guardrails apply: this runs through the guarded provider, so secrets in the chat are
redacted before the LLM sees them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from perfagent.contracts.load_model import HttpMethod, LoadProfileType


class ChatEndpoint(BaseModel):
    method: HttpMethod = HttpMethod.GET
    path: str = Field(..., description="Path like /login or /products.")
    example_body: dict | None = Field(
        default=None,
        description="Request body. For fields that should vary per request, put a "
                    "generator token as the value: ${uuid}, ${randomEmail}, "
                    "${randomInt(min,max)}, ${randomString(n)}, ${timestamp}, "
                    "${randomFrom(a,b,c)}. Keep other values as given.",
    )


class ChatIntent(BaseModel):
    """Structured intent extracted from the user's chat message."""

    target_base_url: str = Field(default="", description="Base URL if the user gave one.")
    goal: str = Field(default="", description="One-line restatement of what to test.")
    endpoints: list[ChatEndpoint] = Field(default_factory=list)
    max_users: int = Field(default=0, description="Peak users if stated, else 0.")
    duration_seconds: int = Field(default=0, description="Duration if stated, else 0.")
    profile_type: LoadProfileType = Field(default=LoadProfileType.RAMP)
    needs_clarification: list[str] = Field(
        default_factory=list,
        description="Questions to ask the user if essential info is missing "
                    "(e.g. target URL, or whether a field should be unique).",
    )
    notes: str = Field(default="", description="Short note on assumptions made.")


CHAT_SYSTEM_PROMPT = """\
You turn a plain-English performance-test request (and/or a pasted API collection) \
into a structured intent. Extract:
- the target base URL (if given),
- the endpoints to test, each with method, path, and an example body where relevant,
- peak users and duration if the user stated them (otherwise leave 0),
- the test type: ramp (default), spike, soak, or stress.

DYNAMIC DATA — this is important:
When the user says a field should be unique, random, or generated (e.g. "unique \
email", "random quantity", "new order id each time"), set that body field's value to \
the matching generator token:
  ${uuid}                -> a unique id
  ${randomEmail}         -> a unique email
  ${randomInt(min,max)}  -> a random integer
  ${randomString(n)}     -> a random string of length n
  ${timestamp}           -> current time
  ${randomFrom(a,b,c)}   -> a random choice
Leave fields the user gave as fixed values alone. Do NOT invent sensitive values \
(passwords, tokens) — leave them as a short placeholder.

If essential information is missing (no target URL, or it's unclear whether a write \
endpoint needs unique data), add a short question to needs_clarification instead of \
guessing. Keep questions minimal — only ask what's truly needed to build a usable test.

Return only the structured intent."""


def build_chat_user_prompt(message: str, collection_text: str = "") -> str:
    parts = [f"User request:\n{message}"]
    if collection_text.strip():
        # Only include a bounded amount; the planner needs structure, not everything.
        snippet = collection_text[:8000]
        parts.append(f"\nPasted API collection (OpenAPI/Postman/HAR or similar):\n{snippet}")
    parts.append(
        "\nExtract the structured intent. Assign generator tokens to any body fields "
        "the user wants unique/random. Ask for anything essential that's missing."
    )
    return "\n".join(parts)
