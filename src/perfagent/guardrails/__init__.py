"""Guardrails — a protective layer around every LLM call.

Usage: wrap any LLMProvider with GuardedProvider. It redacts sensitive data from
the system+user prompts BEFORE they reach the wrapped provider, and scrubs the
response AFTER. Because the whole app calls the LLM through the provider interface,
wrapping once protects every touchpoint (planning and reporting).

    provider = GuardedProvider(build_provider())
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from perfagent.guardrails.output import scrub_output_model
from perfagent.guardrails.redaction import redact, restore

T = TypeVar("T", bound=BaseModel)


class GuardedProvider:
    """Decorates an LLMProvider with input redaction and output scrubbing."""

    def __init__(self, inner, restore_identifiers: bool = True) -> None:
        self._inner = inner
        self._restore = restore_identifiers
        self.name = f"guarded:{getattr(inner, 'name', 'llm')}"
        # last-call telemetry (counts only, never raw values) for logging
        self.last_redaction_counts: dict[str, int] = {}

    def structured(self, *, response_model: type[T], system: str, user: str) -> T:
        # 1. redact both prompts; keep a shared reversible mapping for identifiers
        sys_r = redact(system)
        usr_r = redact(user)
        mapping = {**sys_r.mapping, **usr_r.mapping}
        self.last_redaction_counts = _merge_counts(sys_r.counts, usr_r.counts)

        # 2. call the wrapped provider with redacted prompts only
        result: T = self._inner.structured(
            response_model=response_model,
            system=sys_r.text,
            user=usr_r.text,
        )

        # 3. scrub the output for any leaked sensitive-looking content
        result, _ = scrub_output_model(result)

        # 4. optionally restore reversible identifiers so text reads naturally
        if self._restore and mapping:
            result = _restore_model(result, mapping)
        return result


def _merge_counts(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + v
    return out


def _restore_model(obj: T, mapping: dict[str, str]) -> T:
    data = obj.model_dump()

    def _walk(v):
        if isinstance(v, str):
            return restore(v, mapping)
        if isinstance(v, dict):
            return {k: _walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [_walk(x) for x in v]
        return v

    return obj.__class__.model_validate(_walk(data))


__all__ = ["GuardedProvider", "redact", "restore"]