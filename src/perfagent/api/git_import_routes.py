"""API routes: import performance tests from a Git repository.

  POST /api/git/scan    -> list PerfAgent frameworks/tests and other load scripts
  POST /api/git/import  -> load one PerfAgent test back as an editable plan
  POST /api/git/script  -> read-only view of another (non-PerfAgent) script

The repository URL, branch and token come from the UI for each call. The token is
used only for that call; nothing about the repository is kept except what the user
explicitly imports (the plan and, if committed, its test-data file).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, SecretStr

from perfagent import audit
from perfagent.config import get_settings
from perfagent.data import load_data
from perfagent.db import DataFileRow, PlanRow, get_session
from perfagent.gitexport import ExportError, GitTarget
from perfagent.gitexport.importer import import_test, read_other_script, scan_repo
from perfagent.gitexport.publisher import GitPublishError, cloned_repo

router = APIRouter()


class GitSource(BaseModel):
    # Optional fields checked in code, so a 422 error can never echo the token back.
    repo_url: str = ""
    branch: str = "main"
    git_token: SecretStr | None = None


class ImportBody(GitSource):
    framework_path: str = ""
    test: str = ""
    # Values for the secrets the test needs, e.g. {"PERF_HEADER_AUTHORIZATION": "Bearer ..."}
    secrets: dict[str, SecretStr] = Field(default_factory=dict)
    expected_commit: str | None = None   # commit the user browsed; warn if branch moved


class ScriptBody(GitSource):
    path: str = ""


def _target(src: GitSource) -> GitTarget:
    st = get_settings()
    url = src.repo_url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="enter the Git repository URL")
    token = src.git_token.get_secret_value().strip() if src.git_token else ""
    return GitTarget(
        repo_url=url,
        branch=src.branch.strip() or "main",
        token=token,
        author_name=st.git_author_name,
        author_email=st.git_author_email,
        allowed_hosts=st.git_allowed_hosts.split(","),
        allow_local=st.git_allow_local,
    )


def _errors(fn):
    """Map importer/git failures to clean HTTP errors."""
    try:
        return fn()
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except GitPublishError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/api/git/scan")
def git_scan(body: GitSource) -> dict:
    target = _target(body)

    def run():
        with cloned_repo(target) as (repo, sha):
            scan = scan_repo(repo, sha)
        return {
            "repo_url": target.repo_url,
            "branch": target.branch,
            "commit": scan.commit,
            "truncated": scan.truncated,
            "frameworks": [
                {"name": f.name, "path": f.path, "tool": f.tool,
                 "tests": [t.__dict__ for t in f.tests]}
                for f in scan.frameworks
            ],
            "other_scripts": [s.__dict__ for s in scan.other_scripts],
        }

    return _errors(run)


@router.post("/api/git/import")
def git_import(body: ImportBody) -> dict:
    target = _target(body)
    if not body.test:
        raise HTTPException(status_code=400, detail="choose a test to import")
    secrets = {k: v.get_secret_value() for k, v in body.secrets.items()}

    def run():
        with cloned_repo(target) as (repo, sha):
            imported = import_test(repo, body.framework_path, body.test, secrets)
        return imported, sha

    imported, sha = _errors(run)
    warnings = list(imported.warnings)
    if body.expected_commit and body.expected_commit != sha:
        warnings.insert(0, f"The branch changed since you browsed it; imported the latest commit {sha[:8]}.")

    model = imported.model
    source = f"{target.repo_url}@{target.branch} {imported.framework}/tests/{imported.test} ({sha[:8]})"
    with get_session() as s:
        data_id = data_fields = None
        if imported.data_file:
            fname, content = imported.data_file
            ds = load_data(fname, content)
            row = DataFileRow(filename=fname, source_format=ds.source_format,
                              columns_csv=",".join(ds.fields), row_count=ds.row_count,
                              content=content)
            s.add(row)
            s.flush()
            data_id, data_fields = row.id, ds.fields

        plan = PlanRow(target_base_url=model.target_base_url,
                       goal=f"Imported from Git: {source}"[:1000],
                       load_model_json=model.model_dump_json())
        s.add(plan)
        s.commit()
        plan_id = plan.id

    audit.record("git.imported", entity="plan", entity_id=plan_id, target=model.target_base_url,
                 summary=f"Imported {imported.framework}/tests/{imported.test} from Git ({sha[:8]})")
    return {
        "plan_id": plan_id,
        "load_model": model.model_dump(),
        "framework": imported.framework,
        "framework_path": body.framework_path,
        "test": imported.test,
        "commit": sha,
        "data_file_id": data_id,
        "data_fields": data_fields,
        "missing_secrets": imported.missing_secrets,
        "edited_in_git": imported.edited_in_git,
        "warnings": warnings,
    }


@router.post("/api/git/script")
def git_script(body: ScriptBody) -> dict:
    target = _target(body)
    if not body.path:
        raise HTTPException(status_code=400, detail="choose a script")

    def run():
        with cloned_repo(target) as (repo, _sha):
            return read_other_script(repo, body.path)

    tool, content = _errors(run)
    return {"path": body.path, "tool": tool, "content": content}