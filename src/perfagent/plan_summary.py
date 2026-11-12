"""Small, deterministic summaries shown next to an AI-drafted plan.

Shared by the plan routes (api/app.py) and the conversational chat (perfagent.chat),
so both describe a plan, its guardrail activity and its token usage the same way.
Nothing here calls the LLM.
"""

from __future__ import annotations

REDACTION_LABELS = {
    "EMAIL": "email",
    "JWT": "auth token",
    "APIKEY": "API key",
    "CARD": "card number",
    "SSN": "SSN",
    "HOST": "internal host",
    "PRIVATE_IP": "private IP",
    "INLINE_SECRET": "secret",
    "FIELD": "secret field",
    "URL_HOST": "URL host",
    "QUERY_SECRET": "URL secret",
}


def usage_summary(provider) -> dict:
    """Token usage of the provider's last call, for the UI + audit."""
    u = getattr(provider, "last_usage", None)
    try:
        return u.summary() if u else {}
    except Exception:  # noqa: BLE001
        return {}


def summarize_redactions(counts: dict) -> dict:
    """Turn raw redaction counts into a UI-friendly summary. No raw values, ever."""
    total = sum(counts.values()) if counts else 0
    parts = []
    for key, n in sorted((counts or {}).items()):
        label = REDACTION_LABELS.get(key, key.lower())
        parts.append(f"{n} {label}{'s' if n != 1 else ''}")
    return {"total": total, "detail": ", ".join(parts)}


def plan_rationale(model) -> str:
    """A short, always-accurate explanation of the plan's main choices."""
    scs = model.scenarios or []
    if not scs:
        return ""
    weights = model.normalised_weights()
    # the heaviest journey
    top_i = max(range(len(scs)), key=lambda i: weights[i])
    top = scs[top_i]
    bits = []
    bits.append(
        f"'{top.name}' is weighted highest ({round(weights[top_i]*100)}%) because it's "
        f"treated as the most common user action"
    )
    # correlation note
    has_auth = any(k.lower() == "authorization" for k in (model.headers or {}))
    if has_auth:
        bits.append("the journey logs in first and reuses the token on protected steps")
    # profile note
    bits.append(
        f"load ramps up, holds, then ramps down over {model.load_profile.total_seconds}s "
        "so the system is tested gradually rather than all at once"
    )
    return "; ".join(bits) + "."


__all__ = ["REDACTION_LABELS", "usage_summary", "summarize_redactions", "plan_rationale"]
