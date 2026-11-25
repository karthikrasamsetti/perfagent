"""Project organization; admin aggregates require a server-configured token."""
import json
import secrets
from urllib.parse import urlsplit

from fastapi import Request, APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, func, text

from perfagent.api.project_access import project_grants
from perfagent.api.docs import doc
from perfagent.config import get_settings
from perfagent.contracts.load_model import LoadProfile, Threshold
from perfagent.db import PlanRow, RunResultRow, get_session
from perfagent.db.models import ProjectRow, WorkloadRow
from perfagent.gitexport import slugify, ALL_CI

router = APIRouter()


class ProjectBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    target_url: str = ""
    environment: str = "staging"
    repo_url: str = ""
    branch: str = "main"
    framework_name: str = ""
    ci: list[str] = Field(default_factory=lambda: ["jenkins"])

    @field_validator("ci")
    @classmethod
    def known_ci(cls, values):
        if set(values) - set(ALL_CI):
            raise ValueError("Unknown CI option")
        return list(dict.fromkeys(values))

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Project name is required")
        return value.strip()

    @field_validator("target_url")
    @classmethod
    def valid_target(cls, value):
        if value and (urlsplit(value).scheme not in ("http", "https") or not urlsplit(value).hostname):
            raise ValueError("Use a full HTTP or HTTPS target URL")
        if value and (urlsplit(value).username or urlsplit(value).password):
            raise ValueError("Keep credentials out of project target URLs")
        return value

    @field_validator("repo_url")
    @classmethod
    def credential_free_repo(cls, value):
        if "://" in value and (urlsplit(value).username or urlsplit(value).password):
            raise ValueError("Keep credentials out of repository URLs")
        return value


def project_dict(project):
    return {"project_id": project.id, "name": project.name, "description": project.description,
            "created_at": project.created_at.isoformat(), **json.loads(project.settings_json)}


def require_project(session, project_id):
    if project_id:
        project = session.get(ProjectRow, project_id)
        if project is None:
            raise HTTPException(404, "Project not found")
        return project.id
    project = session.get(ProjectRow, "legacy")
    if project is None:
        project = ProjectRow(id="legacy", name="Imported workspace", description="Existing and unassigned tests",
                             settings_json='{"framework_name":"perfagent-tests","branch":"main"}')
        session.add(project)
        session.flush()
    return project.id


def begin_name_write(session):
    if session.get_bind().dialect.name == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))


def check_test_name(session, project_id, name, *, plan_id=None):
    """Reserve a project-scoped name until the caller commits the plan."""
    key = name.strip().casefold()
    if not project_id or not key:
        return
    session.query(ProjectRow).filter_by(id=project_id).with_for_update().one()
    for row in session.query(PlanRow).filter_by(project_id=project_id):
        if row.id == plan_id:
            continue
        existing = json.loads(row.load_model_json).get("test_name") or row.goal
        if existing and existing.strip().casefold() == key:
            raise HTTPException(409, "A test with that name already exists in this project. Choose a different test name.")


def check_project_name(session, name, *, project_id=None):
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("LOCK TABLE projects IN SHARE ROW EXCLUSIVE MODE"))
    if any(row.id != project_id and row.name.strip().casefold() == name.casefold()
           for row in session.query(ProjectRow)):
        raise HTTPException(409, "A project with that name already exists. Choose a different project name.")


def summary(session, project_id=None):
    query = session.query(func.count(RunResultRow.id), func.coalesce(func.sum(RunResultRow.requests), 0),
                          func.coalesce(func.sum(case((RunResultRow.verdict == "pass", 1), else_=0)), 0))
    query = query.join(PlanRow, RunResultRow.plan_id == PlanRow.id)
    tests = session.query(PlanRow)
    if project_id:
        query = query.filter(PlanRow.project_id == project_id)
        tests = tests.filter(PlanRow.project_id == project_id)
    runs, requests, passes = query.one()
    return {"tests": tests.count(), "runs": runs, "requests": requests,
            "pass_rate": round(passes / runs * 100, 1) if runs else None}


def require_admin(x_perfagent_admin: str | None = Header(default=None)):
    configured = get_settings().admin_api_token.get_secret_value()
    if not configured or not secrets.compare_digest(configured, x_perfagent_admin or ""):
        raise HTTPException(403, "Administrator access requires the configured admin token")


@router.get("/api/projects", **doc("GET", "/api/projects"))
def list_projects(request: Request):
    grants = project_grants(request)
    with get_session() as s:
        projects = s.query(ProjectRow)
        if grants is not None:
            projects = projects.filter(ProjectRow.id.in_(grants))
        return {"projects": [{**project_dict(p), "tests": s.query(PlanRow).filter(PlanRow.project_id == p.id).count()}
                             for p in projects.order_by(ProjectRow.created_at.desc()).all()]}


@router.post("/api/projects", **doc("POST", "/api/projects"))
def create_project(body: ProjectBody):
    settings = body.model_dump(exclude={"name", "description"})
    try:
        settings["framework_name"] = slugify(body.framework_name or body.name, "framework name")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    with get_session() as s:
        begin_name_write(s)
        check_project_name(s, body.name)
        row = ProjectRow(name=body.name, description=body.description, settings_json=json.dumps(settings))
        s.add(row)
        s.commit()
        return project_dict(row)


@router.put("/api/projects/{project_id}", **doc("PUT", "/api/projects/{project_id}"))
def update_project(project_id: str, body: ProjectBody):
    with get_session() as s:
        begin_name_write(s)
        require_project(s, project_id)
        row = s.get(ProjectRow, project_id)
        if row.name.casefold() != body.name.casefold():
            check_project_name(s, body.name, project_id=project_id)
        settings = body.model_dump(exclude={"name", "description"})
        try:
            settings["framework_name"] = slugify(body.framework_name or body.name, "framework name")
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        row.name, row.description, row.settings_json = body.name, body.description, json.dumps(settings)
        s.commit()
        return project_dict(row)


@router.get("/api/projects/{project_id}/dashboard", **doc("GET", "/api/projects/{project_id}/dashboard"))
def project_dashboard(project_id: str):
    with get_session() as s:
        require_project(s, project_id)
        return {"project": project_dict(s.get(ProjectRow, project_id)), "summary": summary(s, project_id)}


@router.get("/api/admin/dashboard", dependencies=[Depends(require_admin)], **doc("GET", "/api/admin/dashboard"))
def admin_dashboard():
    with get_session() as s:
        projects = s.query(ProjectRow).order_by(ProjectRow.name).all()
        return {"summary": summary(s), "projects": [{**project_dict(p), **summary(s, p.id)} for p in projects]}


class AttachBody(BaseModel):
    project_id: str
    test_name: str = Field(default="", max_length=120)


@router.put("/api/plans/{plan_id}/project", **doc("PUT", "/api/plans/{plan_id}/project"))
def attach_test(plan_id: str, body: AttachBody):
    with get_session() as s:
        begin_name_write(s)
        project_id = require_project(s, body.project_id)
        plan = s.get(PlanRow, plan_id)
        if plan is None:
            raise HTTPException(404, "Test not found")
        if plan.project_id not in (None, "legacy", project_id):
            raise HTTPException(409, "This test already belongs to another project. Open it there.")
        model = json.loads(plan.load_model_json)
        name = body.test_name.strip() or model.get("test_name") or plan.goal
        old_name = model.get("test_name") or plan.goal
        if plan.project_id != project_id or old_name.strip().casefold() != name.strip().casefold():
            check_test_name(s, project_id, name, plan_id=plan_id)
        plan.project_id = project_id
        if body.test_name.strip():
            model["test_name"] = name
            plan.load_model_json = json.dumps(model)
        s.commit()
        return {"plan_id": plan_id, "project_id": project_id}


class WorkloadBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    load_profile: LoadProfile
    thresholds: list[Threshold] = Field(default_factory=list)


@router.get("/api/plans/{plan_id}/workloads", **doc("GET", "/api/plans/{plan_id}/workloads"))
def list_workloads(plan_id: str):
    with get_session() as s:
        if s.get(PlanRow, plan_id) is None:
            raise HTTPException(404, "Test not found")
        return {"workloads": [{"workload_id": w.id, "name": w.name, "load_profile": json.loads(w.profile_json),
                               "thresholds": json.loads(w.thresholds_json)}
                              for w in s.query(WorkloadRow).filter(WorkloadRow.plan_id == plan_id).all()]}


@router.post("/api/plans/{plan_id}/workloads", **doc("POST", "/api/plans/{plan_id}/workloads"))
def save_workload(plan_id: str, body: WorkloadBody):
    if not body.name.strip():
        raise HTTPException(400, "Workload name is required")
    with get_session() as s:
        if s.get(PlanRow, plan_id) is None:
            raise HTTPException(404, "Test not found")
        row = s.query(WorkloadRow).filter_by(plan_id=plan_id, name=body.name.strip()).first()
        if row is None:
            row = WorkloadRow(plan_id=plan_id, name=body.name.strip())
            s.add(row)
        row.profile_json = body.load_profile.model_dump_json()
        row.thresholds_json = json.dumps([t.model_dump() for t in body.thresholds])
        s.commit()
        return {"workload_id": row.id, "name": row.name}
