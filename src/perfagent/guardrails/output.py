"""Output guardrail — validates what comes back from the LLM.

The schema-level validation is already handled by Instructor + Pydantic (the
response must match the requested model). This adds a content check: the model's
free-text output must not contain anything that looks like leaked sensitive data
(e.g. if a prompt-injection tried to make it emit a token). Any hit is scrubbed.
"""

from __future__ import annotations

from pydantic import BaseModel

from perfagent.guardrails.redaction import redact

def scrub_output_text(text: str) -> tuple[str, bool]:
    """Redact any sensitive-looking content the model produced.

    Returns (clean_text, was_modified). Reversible identifiers are NOT restored
    here — if the model emitted something that looks like a secret, we remove it.
    """
    result = redact(text)
    modified = bool(result.counts)
    return (result.text if modified else text), modified


def scrub_output_model(obj: BaseModel) -> tuple[BaseModel, bool]:
    """Scrub every string field of a returned Pydantic object."""
    modified_any = False
    data = obj.model_dump()

    def _walk(v):
        nonlocal modified_any
        if isinstance(v, str):
            cleaned, m = scrub_output_text(v)
            modified_any = modified_any or m
            return cleaned
        if isinstance(v, dict):
            return {k: _walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [_walk(x) for x in v]
        return v

    cleaned = _walk(data)
    return obj.__class__.model_validate(cleaned), modified_any