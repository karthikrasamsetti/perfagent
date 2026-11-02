"""Guardrails — a protective layer around every LLM call.

Wrap any LLMProvider with GuardedProvider. It redacts sensitive data from the
system+user prompts BEFORE they reach the wrapped provider, and scrubs the response
AFTER. Because the whole app calls the LLM through the provider interface, wrapping
once protects every touchpoint (planning and reporting).

    provider = GuardedProvider(build_provider())

GUARDRAIL DEBUG MODE (for verifying redaction before testing real endpoints):
  Set the env var GUARDRAIL_DEBUG=1 to log the REDACTED prompts actually sent to the
  LLM, plus redaction counts and output-scrub results. It logs only the *redacted*
  text — never the raw original — so you can confirm no secret survives, without
  writing real secrets to the log. Turn it OFF for normal use.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from perfagent.guardrails.output import scrub_output_model
from perfagent.guardrails.redaction import redact, restore
from perfagent.logging_config import get_logger

T = TypeVar("T", bound=BaseModel)

_log = get_logger("perfagent.guardrails")


def _debug_on() -> bool:
    try:
        from perfagent.config import get_settings
        return bool(get_settings().guardrail_debug)
    except Exception:  # noqa: BLE001
        return False


class GuardedProvider:
    """Decorates an LLMProvider with input redaction and output scrubbing."""

    def __init__(self, inner, restore_identifiers: bool = True) -> None:
        self._inner = inner
        self._restore = restore_identifiers
        self.name = f"guarded:{getattr(inner, 'name', 'llm')}"
        self.last_redaction_counts: dict[str, int] = {}

    def structured(self, *, response_model: type[T], system: str, user: str) -> T:
        # 1. Redact the USER prompt only — that's where user-supplied data (and any
        #    secrets) live. The SYSTEM prompt is our own fixed instructions with no
        #    user data, so redacting it is pointless and would garble the instructions
        #    (e.g. the word "extract" being mistaken for a field). Leave it intact.
        usr_r = redact(user)
        mapping = dict(usr_r.mapping)
        self.last_redaction_counts = dict(usr_r.counts)

        debug = _debug_on()
        if debug:
            # Log ONLY the redacted user text that will actually be sent to the LLM.
            _log.info(
                "guardrail.debug.sent_to_llm",
                redaction_counts=self.last_redaction_counts,
                user_redacted=usr_r.text,
            )

        # 2. call the wrapped provider: system prompt as-is, user prompt redacted
        result: T = self._inner.structured(
            response_model=response_model,
            system=system,
            user=usr_r.text,
        )

        # 3. scrub the output for any leaked sensitive-looking content
        result, scrubbed = scrub_output_model(result)
        if debug:
            _log.info("guardrail.debug.output_scrubbed", output_modified=scrubbed)

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