"""Enforce explicit project grants for authenticated managed workspace requests."""

from fastapi import HTTPException, Request

from perfagent.api import access
from perfagent.db import PlanRow, RunResultRow, ScriptRow, get_session

# Endpoints with no project data, including execution routes with their own managed denial.
_WORKSPACE_ROUTES = {
    ("GET", "/api/tools"),
    ("GET", "/api/workspace/session"),
    ("GET", "/api/run/available"),
    ("GET", "/api/projects"),
    ("POST", "/api/preflight"),
    ("POST", "/api/scripts/{script_id}/run"),
    ("POST", "/api/jenkins/trigger"),
}
_QUERY_SCOPED = {
    ("GET", "/api/plans"),
    ("GET", "/api/runs"),
    ("GET", "/api/reporting/runs"),
}
_PROJECT_ROUTES = {
    ("GET", "/api/projects/{project_id}/dashboard"): ("project_id", "viewer"),
    ("PUT", "/api/projects/{project_id}"): ("project_id", "editor"),
    ("GET", "/api/plans/{plan_id}"): ("plan_id", "editor"),
    ("GET", "/api/plans/{plan_id}/workloads"): ("plan_id", "viewer"),
    ("POST", "/api/plans/{plan_id}/workloads"): ("plan_id", "editor"),
    ("GET", "/api/reporting/trend"): ("plan_id", "viewer"),
    ("GET", "/api/scripts/{script_id}/readiness"): ("script_id", "viewer"),
    ("GET", "/api/scripts/{script_id}/download"): ("script_id", "editor"),
    ("POST", "/api/scripts/{script_id}/validate"): ("script_id", "editor"),
    ("POST", "/api/scripts/{script_id}/edit"): ("script_id", "editor"),
    ("GET", "/api/runs/{result_id}/saved-report"): ("result_id", "viewer"),
    ("GET", "/api/runs/{run_id}/report/download"): ("run_id", "viewer"),
    ("PUT", "/api/runs/{run_id}/release-policy"): ("run_id", "editor"),
}


def project_grants(request: Request) -> dict | None:
    """Return grants keyed by project ID, or None for local mode."""
    settings = access.get_settings()
    if settings.perfagent_access_mode == "local":
        return None
    principal = getattr(request.state, "principal", None)
    return settings.perfagent_project_grants.get(principal.subject, {}) if principal else {}


def enforce_project_access(request: Request) -> None:
    route = request.scope["route"].path
    if not route.startswith("/api/"):
        return
    grants = project_grants(request)
    key = (request.method, route)
    if grants is None or key in _WORKSPACE_ROUTES:
        return
    if key == ("POST", "/api/scripts/{script_id}/validate") and not access.get_settings().perfagent_managed_k6_image:
        access.require_local_execution()
    if key in _QUERY_SCOPED:
        field, role = "project_id", "viewer"
    elif key in _PROJECT_ROUTES:
        field, role = _PROJECT_ROUTES[key]
    else:
        raise HTTPException(403, "This operation is unavailable in managed workspaces.")

    identifier = request.path_params.get(field) or request.query_params.get(field)
    if not identifier or len(identifier) > 32:
        raise HTTPException(403, "A permitted project scope is required.")
    project_id = identifier if field == "project_id" else _resource_project(field, identifier)
    granted = grants.get(project_id)
    if granted != "editor" and (granted != "viewer" or role == "editor"):
        raise HTTPException(404, "Project resource not found.")


def _resource_project(field: str, identifier: str) -> str | None:
    with get_session() as session:
        if field == "plan_id":
            plan_id = identifier
        else:
            model = ScriptRow if field == "script_id" else RunResultRow
            resource = session.get(model, identifier)
            if resource is None:
                return None
            plan_id = resource.plan_id
        plan = session.get(PlanRow, plan_id)
        return plan.project_id if plan else None
