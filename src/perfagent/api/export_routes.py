"""API routes: export an approved k6 test as a Git-ready performance framework.

  GET  /api/export/settings                -> allowed Git hosts, CI options
  POST /api/scripts/{script_id}/export/git -> build framework, commit + push to Git
  POST /api/scripts/{script_id}/export/zip -> same framework as a .zip download
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import select

from perfagent import audit, integrations
from perfagent.api.docs import doc
from perfagent.config import get_settings
from perfagent.contracts.load_model import LoadModel
from perfagent.db import DataFileRow, PlanRow, ScriptRow, get_session
from perfagent.generator import render
from perfagent.gitexport import ALL_CI, ExportError, GitTarget, build_framework, publish, slugify
from perfagent.gitexport.publisher import GitPublishError

router = APIRouter()


class ExportBody(BaseModel):
    # Defaults instead of required fields, and checked in code: FastAPI's 422 error
    # for a missing field echoes the whole request body, which would include the token.
    framework_name: str = Field("", description="Framework folder name, e.g. 'payments-perf'")
    test_name: str = Field("", description="Test folder name, e.g. 'checkout-peak'")
    repo_url: str = ""                 # https://... or git@host:org/repo.git
    branch: str = "main"
    # Access token typed in the UI. SecretStr keeps it out of logs, reprs and error
    # messages; it is used for this one push and never stored.
    git_token: SecretStr | None = None
    ci: list[str] = Field(default_factory=lambda: list(ALL_CI))
    include_data: bool = False         # commit the test-data file (off by default)
    data_file_id: str | None = None
    commit_message: str | None = None


def _load(script_id: str, body: ExportBody) -> tuple[LoadModel, str, tuple[str, str] | None]:
    """Fetch the script's plan and verify the plan still produces this exact script."""
    with get_session() as s:
        script = s.get(ScriptRow, script_id)
        if script is None:
            raise HTTPException(status_code=404, detail="script not found")
        if script.tool != "k6":
            raise HTTPException(status_code=400, detail="pipeline export supports k6 scripts only")
        plan = s.get(PlanRow, script.plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="plan for this script not found")
        if (plan.goal or "").startswith("Uploaded script"):
            raise HTTPException(
                status_code=400,
                detail="uploaded scripts can't be saved to Git yet - only scripts generated from a "
                       "plan, because PerfAgent can't reliably separate secrets from hand-written code",
            )
        model = LoadModel.model_validate_json(plan.load_model_json)

        # The plan row is updated on every Generate. If it no longer renders to this
        # script, the user edited the plan afterwards: export only what they saw.
        if render(model, "k6")[1] != script.content:
            raise HTTPException(
                status_code=409,
                detail="the plan changed after this script was generated; generate again, then export",
            )

        data = None
        if model.data_file:
            row = s.get(DataFileRow, body.data_file_id) if body.data_file_id else None
            if row is None or row.filename != model.data_file.filename:
                row = s.scalars(
                    select(DataFileRow)
                    .where(DataFileRow.filename == model.data_file.filename)
                    .order_by(DataFileRow.created_at.desc())
                ).first()
            if row is not None:
                data = (row.filename, row.content)
            elif body.include_data:
                raise HTTPException(status_code=400, detail="the plan's data file is no longer stored")
        return model, script.plan_id, data


def _build(repo: Path, script_id: str, body: ExportBody, model, plan_id, data):
    return build_framework(
        repo,
        framework_name=body.framework_name,
        test_name=body.test_name,
        model=model,
        plan_id=plan_id,
        script_id=script_id,
        data_file=data,
        include_data=body.include_data,
        ci=body.ci,
    )


def _display_repo(url: str) -> str:
    """Repository URL for logs: never includes credentials (they're rejected anyway)."""
    return url.split("@")[-1] if url.startswith("https://") else url


@router.get("/api/export/settings", **doc("GET", "/api/export/settings"))
def export_settings() -> dict:
    st = get_settings()
    hosts = [h.strip() for h in st.git_allowed_hosts.split(",") if h.strip()]
    return {"allowed_hosts": hosts, "ci_options": list(ALL_CI)}


@router.post("/api/scripts/{script_id}/export/git", **doc("POST", "/api/scripts/{script_id}/export/git"))
def export_git(script_id: str, body: ExportBody) -> dict:
    st = get_settings()
    try:
        fw, test = slugify(body.framework_name, "framework name"), slugify(body.test_name, "test name")
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    repo_url = body.repo_url.strip()
    token = body.git_token.get_secret_value().strip() if body.git_token else ""
    if not repo_url:
        raise HTTPException(status_code=400, detail="enter the Git repository URL")
    if repo_url.startswith("https://") and not token:
        raise HTTPException(status_code=400, detail="enter an access token that can push to this repository")

    model, plan_id, data = _load(script_id, body)
    target = GitTarget(
        repo_url=repo_url,
        branch=body.branch.strip() or "main",
        token=token,
        author_name=st.git_author_name,
        author_email=st.git_author_email,
        allowed_hosts=st.git_allowed_hosts.split(","),
        allow_local=st.git_allow_local,
    )
    built: dict = {}

    def build(repo: Path) -> list[str]:
        res = _build(repo, script_id, body, model, plan_id, data)
        built["result"] = res
        return res.files

    message = body.commit_message or f"perf({fw}): add/update test '{test}' (plan {plan_id[:8]})"
    try:
        pub = publish(target, build, message)
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except GitPublishError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    res = built["result"]
    integrations.save(plan_id, git={"repo_url": pub.repo_url, "branch": pub.branch,
                                    "framework": res.framework, "test": res.test, "ci": body.ci})
    audit.record(
        "git.pushed" if pub.changed else "git.push_unchanged", entity="script", entity_id=script_id,
        target=model.target_base_url,
        summary=(f"{res.framework}/tests/{res.test} -> {_display_repo(pub.repo_url)}@{pub.branch}"
                 + (f" ({pub.commit[:8]})" if pub.commit else " (no changes)")),
    )
    return {
        "framework": res.framework,
        "test": res.test,
        "repo_url": pub.repo_url,
        "branch": pub.branch,
        "commit": pub.commit,
        "changed": pub.changed,
        "files": res.files,
        "required_secrets": res.required_secrets,
        "warnings": res.warnings,
    }


@router.post("/api/scripts/{script_id}/export/zip", **doc("POST", "/api/scripts/{script_id}/export/zip"))
def export_zip(script_id: str, body: ExportBody) -> Response:
    try:
        slugify(body.framework_name, "framework name"), slugify(body.test_name, "test name")
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    model, plan_id, data = _load(script_id, body)
    with tempfile.TemporaryDirectory(prefix="perfagent_zip_") as tmp:
        root = Path(tmp)
        try:
            res = _build(root, script_id, body, model, plan_id, data)
        except ExportError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in res.files:
                zf.write(root / rel, rel)
    audit.record("git.exported_zip", entity="script", entity_id=script_id,
                 target=model.target_base_url,
                 summary=f"Downloaded framework {res.framework}/tests/{res.test} as .zip")
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{res.framework}.zip"',
            "X-Required-Secrets": ",".join(res.required_secrets),
        },
    )