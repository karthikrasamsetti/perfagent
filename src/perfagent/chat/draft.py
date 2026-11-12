"""The conversation's structured draft — what the chat is actually building.

The chat text is not the source of truth; this draft is. Each turn the model returns a
ChatTurn (a short reply + the full updated draft). Code then:

  - merges it into the previous draft (``merge_intent``) so a turn can't silently
    drop something the user said earlier,
  - decides what is still missing (``assess``) — the model never decides "ready".

The draft reuses ChatIntent from the single-shot describe step, so both paths feed
the same planner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from perfagent.chat_intent import ChatEndpoint, ChatIntent
from perfagent.contracts.load_model import LoadProfileType

# Used when the user never states a size — the same defaults as the single-shot path.
DEFAULT_USERS = 20
DEFAULT_DURATION_SECONDS = 60

_REDACTION_MARK = "_REDACTED>"


class ChatTurn(BaseModel):
    """What the model returns for one conversation turn. Schema-validated."""

    reply: str = Field(
        default="",
        description="A short, friendly reply to the user (1-3 sentences). Confirm what "
                    "you understood or changed. If something essential is missing, ask "
                    "for it here — at most two questions per turn.",
    )
    intent: ChatIntent = Field(
        default_factory=ChatIntent,
        description="The FULL updated draft after this turn: carry over everything from "
                    "the current draft that the user did not change.",
    )
    wants_plan: bool = Field(
        default=False,
        description="True only if the user's latest message asks to go ahead and build "
                    "the plan now (e.g. 'looks good', 'go ahead', 'build it').",
    )


@dataclass
class Readiness:
    """Code's verdict on whether the draft is enough to build a plan."""

    missing: list[str] = field(default_factory=list)     # machine keys: target | endpoints
    prompts: list[str] = field(default_factory=list)     # the matching questions
    assumed: dict[str, bool] = field(default_factory=dict)  # sizes the user never stated

    @property
    def ready(self) -> bool:
        return not self.missing


# ---------- normalisation ----------

def _normalise_base_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if not (url.startswith("http://") or url.startswith("https://")):
        return ""            # not usable as a target — treated as still missing
    return url


def _normalise_path(path: str, base_url: str = "") -> str:
    """Make a path the planner accepts: starts with '/', no host."""
    path = (path or "").strip()
    if path.startswith("http://") or path.startswith("https://"):
        parts = urlsplit(path)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
    if not path.startswith("/"):
        path = "/" + path
    return path


def _normalise_endpoints(endpoints: list[ChatEndpoint], base_url: str) -> list[ChatEndpoint]:
    """Clean paths and drop exact duplicates (same method + path), keeping the first."""
    out: list[ChatEndpoint] = []
    seen: set[tuple[str, str]] = set()
    for ep in endpoints:
        path = _normalise_path(ep.path, base_url)
        key = (ep.method.value, path)
        if key in seen:
            continue
        seen.add(key)
        out.append(ChatEndpoint(method=ep.method, path=path, example_body=ep.example_body))
    return out


# ---------- merge ----------

def merge_intent(previous: ChatIntent, new: ChatIntent) -> ChatIntent:
    """Fold this turn's draft into the previous one — deterministically.

    "Not stated" values in the new draft (empty string, 0, empty list) never erase
    what was already known; anything the model did state wins. The endpoint list is
    replaced as a whole when the model returns one, so "drop /checkout" works.
    """
    target = _normalise_base_url(new.target_base_url) or previous.target_base_url
    endpoints = new.endpoints if new.endpoints else previous.endpoints
    return ChatIntent(
        target_base_url=target,
        goal=(new.goal or "").strip() or previous.goal,
        endpoints=_normalise_endpoints(list(endpoints), target),
        max_users=new.max_users if new.max_users > 0 else previous.max_users,
        duration_seconds=(new.duration_seconds if new.duration_seconds > 0
                          else previous.duration_seconds),
        profile_type=new.profile_type or previous.profile_type or LoadProfileType.RAMP,
        needs_clarification=[q.strip() for q in new.needs_clarification if q and q.strip()],
        notes=(new.notes or "").strip(),
    )


# ---------- readiness ----------

def assess(intent: ChatIntent) -> Readiness:
    """Decide what's still needed before a plan can be built. Code decides, not the AI."""
    r = Readiness()
    if not _normalise_base_url(intent.target_base_url):
        r.missing.append("target")
        r.prompts.append("What's the target base URL (e.g. https://staging.example.com)?")
    if not intent.endpoints:
        r.missing.append("endpoints")
        r.prompts.append("Which endpoints should I test (method + path)?")
    r.assumed = {
        "max_users": intent.max_users <= 0,
        "duration_seconds": intent.duration_seconds <= 0,
    }
    return r


def has_masked_values(intent: ChatIntent) -> bool:
    """True if a request body still carries a guardrail placeholder (a masked secret)."""
    for ep in intent.endpoints:
        if ep.example_body and _REDACTION_MARK in json.dumps(ep.example_body):
            return True
    return False


def draft_view(intent: ChatIntent, readiness: Readiness) -> dict:
    """The draft as the UI shows it, with the defaults that will apply filled in."""
    return {
        "target_base_url": intent.target_base_url,
        "goal": intent.goal,
        "profile_type": intent.profile_type.value,
        "max_users": intent.max_users or DEFAULT_USERS,
        "duration_seconds": intent.duration_seconds or DEFAULT_DURATION_SECONDS,
        "assumed": readiness.assumed,
        "endpoints": [
            {"method": e.method.value, "path": e.path, "example_body": e.example_body}
            for e in intent.endpoints
        ],
        "notes": intent.notes,
        "secrets_masked": has_masked_values(intent),
    }


__all__ = [
    "ChatTurn", "Readiness", "merge_intent", "assess", "draft_view", "has_masked_values",
    "DEFAULT_USERS", "DEFAULT_DURATION_SECONDS",
]
