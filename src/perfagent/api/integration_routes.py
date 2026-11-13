"""API routes: saved (non-secret) Git and Jenkins details.

  GET    /api/integrations?plan_id=...              details for a plan (+ last-used defaults)
  DELETE /api/integrations?plan_id=...&section=...  forget 'git', 'jenkins' or 'all'

Details are saved automatically by the push / import / Jenkins routes after a successful
action. Tokens are never stored, so they are never returned here either.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from perfagent import audit, integrations
from perfagent.api.docs import doc

router = APIRouter()


@router.get("/api/integrations", **doc("GET", "/api/integrations"))
def get_integrations(plan_id: str | None = None) -> dict:
    return integrations.get(plan_id)


@router.delete("/api/integrations", **doc("DELETE", "/api/integrations"))
def forget_integrations(section: str, plan_id: str | None = None) -> dict:
    try:
        integrations.forget(plan_id, section)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    audit.record("integrations.forgotten", entity="plan", entity_id=(plan_id or "")[:32],
                 summary=f"Saved {section} details removed")
    return integrations.get(plan_id)