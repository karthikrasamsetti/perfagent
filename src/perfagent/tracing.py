"""Tracing — record each LLM call (step, model, tokens, latency, status) for debugging.

A thin helper (like audit) plus a contextvar so the GuardedProvider knows which step
it's serving (plan / chat / dynamize / narrate) when it records the trace.
"""

from __future__ import annotations

import contextvars

from perfagent.db import TraceRow, get_session
from perfagent.logging_config import get_logger

_log = get_logger("perfagent.trace")

# the current AI step (set by the API before a provider call)
_current_step: contextvars.ContextVar[str] = contextvars.ContextVar("ai_step", default="")


def set_step(step: str) -> None:
    _current_step.set(step)


def current_step() -> str:
    return _current_step.get()


def record(*, step: str, model: str, prompt_tokens: int, completion_tokens: int,
           latency_ms: int, status: str = "ok", redactions: int = 0,
           error: str = "") -> None:
    """Record a trace of one LLM call. Best-effort — never breaks the request."""
    try:
        with get_session() as s:
            s.add(TraceRow(
                step=step or "llm", model=model,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                latency_ms=latency_ms, status=status, redactions=redactions,
                error=error[:500],
            ))
            s.commit()
    except Exception as e:  # noqa: BLE001
        _log.warning("trace.write_failed", error=str(e))
    _log.info("trace", step=step, model=model,
              tokens=prompt_tokens + completion_tokens, latency_ms=latency_ms,
              status=status)


def recent(limit: int = 100) -> list[dict]:
    """Return recent traces (newest first) for the Traces view."""
    with get_session() as s:
        rows = (s.query(TraceRow)
                .order_by(TraceRow.created_at.desc())
                .limit(limit).all())
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "step": r.step,
                "model": r.model,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.prompt_tokens + r.completion_tokens,
                "latency_ms": r.latency_ms,
                "status": r.status,
                "redactions": r.redactions,
                "error": r.error,
            }
            for r in rows
        ]
