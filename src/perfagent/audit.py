"""Audit trail — record consequential actions durably, and log them.

One call, record(...), writes an AuditRow and emits a structured log line, so the
activity log (DB) and the debug logs (file/console) stay in sync. Never pass secrets
or raw bodies here — ids, targets, counts, and a short human summary only.
"""

from __future__ import annotations

from perfagent.db import AuditRow, get_session
from perfagent.logging_config import get_logger

_log = get_logger("perfagent.audit")


def record(action: str, *, entity: str = "", entity_id: str = "",
           target: str = "", summary: str = "", actor: str = "local") -> None:
    """Write an audit row and log it. Best-effort — never breaks the request."""
    try:
        with get_session() as s:
            s.add(AuditRow(
                action=action, entity=entity, entity_id=entity_id,
                target=target, summary=summary, actor=actor,
            ))
            s.commit()
    except Exception as e:  # noqa: BLE001
        _log.warning("audit.write_failed", action=action, error=str(e))
    # always log the event too
    _log.info("audit", action=action, entity=entity, entity_id=entity_id,
              target=target, summary=summary)


def recent(limit: int = 100) -> list[dict]:
    """Return the most recent audit events (newest first) for the activity log."""
    with get_session() as s:
        rows = (s.query(AuditRow)
                .order_by(AuditRow.created_at.desc())
                .limit(limit).all())
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "action": r.action,
                "entity": r.entity,
                "entity_id": r.entity_id,
                "target": r.target,
                "summary": r.summary,
                "actor": r.actor,
            }
            for r in rows
        ]
