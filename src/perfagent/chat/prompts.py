"""Prompts for the conversational planner.

Each turn the model gets: the current structured draft, what code says is still
missing, the recent messages, and the latest user message. It returns a ChatTurn.
Because the draft carries the conversation's state, only a short window of messages
is replayed — long chats don't grow the prompt.
"""

from __future__ import annotations

import json

from perfagent.chat_intent import ChatIntent

# Pasted collections are bounded: the model needs the structure, not every byte.
MAX_COLLECTION_CHARS = 8000

CONVERSATION_SYSTEM_PROMPT = """\
You are the planning assistant of a performance-testing agent. You hold a short \
conversation with the user to work out WHAT to load test, and you keep a structured \
draft up to date. You never run anything — a human reviews and approves the plan later.

Each turn you receive the current draft, the list of essentials still missing, the \
recent conversation, and the user's latest message. Return:
- intent: the FULL updated draft. Start from the current draft and apply only what \
the latest message changes. Never drop endpoints, the target, or sizes the user did \
not ask to change. If the user asks to remove an endpoint, return the list without it.
- reply: 1-3 friendly sentences. Say what you understood or changed. If essentials \
are missing, ask for them — at most two questions per turn, the most important first.
- wants_plan: true only when the latest message clearly asks to go ahead and build \
the plan ("looks good", "go ahead", "build it", "yes, create the plan").

What goes in the draft:
- target_base_url: scheme + host (+ port) only, e.g. https://staging.example.com.
- endpoints: method, path (starting with /), and an example body where relevant. \
Only use endpoints the user gave or that appear in a pasted collection. Never invent paths.
- max_users and duration_seconds: only if the user stated them, otherwise 0. Convert \
"2 minutes" to 120.
- profile_type: ramp (default), spike, soak, or stress.
- goal: a one-line restatement of what is being tested.
- needs_clarification: open questions that would improve the test but do not block it.
- notes: a short note on assumptions you made.

DYNAMIC DATA:
When the user says a field should be unique, random, or generated, set that body \
field's value to the matching generator token:
  ${uuid}                -> a unique id
  ${randomEmail}         -> a unique email
  ${randomInt(min,max)}  -> a random integer
  ${randomString(n)}     -> a random string of length n
  ${timestamp}           -> current time
  ${randomFrom(a,b,c)}   -> a random choice
Leave fixed values alone. Values shown as <..._REDACTED> were masked for safety: keep \
them exactly as they are and never guess what they were. Do not invent passwords or tokens.

Do not ask for information that is already in the draft. Do not ask about the load \
ramp shape, thresholds or correlation — those are handled after the plan is drafted. \
Return only the structured result.\
"""

_MISSING_LABELS = {
    "target": "the target base URL",
    "endpoints": "at least one endpoint (method + path)",
}


def _draft_json(intent: ChatIntent) -> str:
    data = intent.model_dump(mode="json", exclude={"needs_clarification", "notes"})
    return json.dumps(data, indent=2)


def build_turn_prompt(
    *,
    intent: ChatIntent,
    missing: list[str],
    history: list[dict],
    message: str,
    collection_text: str = "",
) -> str:
    """Build the user prompt for one turn.

    ``history`` is the recent transcript *before* the latest message, oldest first.
    """
    parts: list[str] = []
    parts.append("Current draft (JSON):\n" + _draft_json(intent))

    if missing:
        labels = ", ".join(_MISSING_LABELS.get(m, m) for m in missing)
        parts.append(f"Essentials still missing before a plan can be built: {labels}.")
    else:
        parts.append("All essentials are present — a plan can be built whenever the "
                     "user is happy with the draft.")

    if history:
        lines = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history]
        parts.append("Recent conversation (oldest first):\n" + "\n".join(lines))

    parts.append("Latest user message:\n" + message)

    if collection_text.strip():
        parts.append(
            "Pasted API collection (OpenAPI/Postman/HAR or similar) — take endpoints "
            "from it:\n" + collection_text[:MAX_COLLECTION_CHARS]
        )

    parts.append("Return the full updated draft, a short reply, and wants_plan.")
    return "\n\n".join(parts)


__all__ = ["CONVERSATION_SYSTEM_PROMPT", "MAX_COLLECTION_CHARS", "build_turn_prompt"]
