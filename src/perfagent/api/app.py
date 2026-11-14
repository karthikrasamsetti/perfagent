"""FastAPI service — the agent's API plus the web UI.

Endpoints:
  GET  /                          -> the web UI (HTML)
  GET  /api/tools                 -> supported tools (k6 first)
  POST /api/data                  -> upload + parse + validate a test-data file
  POST /api/plan                  -> AI drafts a LoadModel, saved; returns it for review
  POST /api/plan/{id}/generate    -> render a saved (possibly edited) plan to a script
  GET  /api/plans                 -> list saved plans
  GET  /api/plans/{id}            -> one plan + its scripts (lineage)
  GET  /api/scripts/{id}/download -> download a script file
  POST /api/scripts/{id}/run      -> launch a live run
  GET  /api/runs/{id}             -> live status + metrics
  POST /api/runs/{id}/stop        -> stop a run
  GET  /api/runs/{id}/report      -> verdict + narrative
  /api/chat/sessions...           -> conversational planning (see api/chat_routes.py)
  POST /api/load-profile          -> build the load stages (deterministic)
  POST /api/request-preview       -> the requests a plan will send (nothing is sent)
  GET  /api/data/{id}             -> columns + first rows of an uploaded data file

Every endpoint is documented in api/docs.py (group, summary, access level).
  GET  /api/health                -> app + database status (which database is in use)

Start with:  uv run uvicorn perfagent.api.app:app --reload
Then open:   http://127.0.0.1:8080
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from perfagent import __version__, audit, tracing
from perfagent.analyzer.baseline import compare, metrics_from_snapshot, no_baseline
from perfagent.analyzer.diagnostics import diagnose
from perfagent.api.chat_routes import router as chat_router
from perfagent.api.docs import API_DESCRIPTION, API_TITLE, TAGS, doc
from perfagent.api.export_routes import router as export_router
from perfagent.api.git_import_routes import router as git_import_router
from perfagent.api.integration_routes import router as integration_router
from perfagent.api.jenkins_routes import router as jenkins_router
from perfagent.check_suggest import (
    CHECK_SUGGEST_SYSTEM_PROMPT,
    SuggestedChecks,
    build_check_suggest_prompt,
)
from perfagent.contracts.artifacts import PlanArtifact
from perfagent.contracts.load_model import (
    ROW_MODES,
    DataFile,
    LoadModel,
    LoadProfileType,
)
from perfagent.data import DataValidationError, load_data
from perfagent.db import DataFileRow, PlanRow, RunResultRow, ScriptRow, SlaProfileRow, get_session
from perfagent.dynamize import DYNAMIZE_SYSTEM_PROMPT, DynamizedBody, build_dynamize_user_prompt
from perfagent.evaluation import evaluate_plan, evaluate_report
from perfagent.generator import generate_script, supported_tools
from perfagent.importers import ImportError_, import_endpoints
from perfagent.logging_config import configure as _configure_logging
from perfagent.logging_config import get_logger
from perfagent.plan_summary import (
    plan_rationale as _plan_rationale,
)
from perfagent.plan_summary import (
    summarize_redactions as _summarize_redactions,
)
from perfagent.plan_summary import (
    usage_summary as _usage_summary,
)
from perfagent.planner import PlanRequest, draft_plan
from perfagent.planner.profile import build_profile
from perfagent.preflight import preflight
from perfagent.providers import build_provider
from perfagent.request_data import preview_requests
from perfagent.runner import get_run, k6_available, start_run, stop_run
from perfagent.runner.validator import validate_script

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=__version__,
    openapi_tags=TAGS,
)
app.include_router(export_router)
app.include_router(git_import_router)
app.include_router(jenkins_router)
app.include_router(integration_router)
app.include_router(chat_router)
_configure_logging()
_log = get_logger("perfagent.api")

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"


# ---------- request/response models ----------

class GenerateBody(BaseModel):
    tool: str = "k6"
    # Optional: the (possibly human-edited) LoadModel to use instead of the stored one.
    load_model: LoadModel | None = None
    # Optional: id of an uploaded data file to attach to this plan for the run.
    data_file_id: str | None = None
    # Optional: how its rows are handed out — random | sequential | unique.
    data_row_mode: str | None = None
    # Optional: global headers to apply to every request (e.g. Authorization).
    headers: dict[str, str] | None = None


# ---------- guardrail / usage / rationale summaries ----------
# Shared with the conversational chat — see perfagent/plan_summary.py.

# ---------- health ----------

@app.get("/api/health", **doc("GET", "/api/health"))
def health() -> dict:
    """Is the app up and can it reach its database? Also says WHICH database is in
    use (SQLite or Postgres) and whether its schema is current — handy after
    switching DATABASE_URL, and usable as a container health check."""
    from sqlalchemy import text

    from perfagent.db import models as dbmodels
    from perfagent.db.migrate import current_revision, head_revision

    try:
        engine = dbmodels.get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        revision = current_revision(engine)
    except Exception as e:  # noqa: BLE001
        _log.error("health.database_unavailable", error=f"{type(e).__name__}: {e}"[:300])
        raise HTTPException(status_code=503, detail="database unavailable") from e
    url = engine.url
    return {
        "status": "ok",
        "database": {
            "backend": engine.dialect.name,                 # 'sqlite' | 'postgresql'
            "host": url.host or "",
            "name": url.database or "",
            "schema_revision": revision,
            "schema_up_to_date": revision == head_revision(),
        },
    }


# ---------- UI ----------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return (_WEB_DIR / "index.html").read_text(encoding="utf-8")


# ---------- API ----------

@app.get("/api/tools", **doc("GET", "/api/tools"))
def tools() -> dict:
    return {"tools": supported_tools()}



@app.get("/api/audit", **doc("GET", "/api/audit"))
def get_audit(limit: int = 100) -> dict:
    """Return recent audit events for the activity log."""
    return {"events": audit.recent(limit=limit)}


@app.get("/api/usage/total", **doc("GET", "/api/usage/total"))
def usage_total() -> dict:
    """Total LLM token usage + rough cost across all AI calls (for the top-bar chip)."""
    return audit.totals()


@app.get("/api/traces", **doc("GET", "/api/traces"))
def get_traces(limit: int = 100) -> dict:
    """Recent AI-call traces (step, model, tokens, latency, status) for debugging."""
    return {"traces": tracing.recent(limit=limit)}


@app.get("/api/runs", **doc("GET", "/api/runs"))
def list_runs(limit: int = 50) -> dict:
    """List past runs (with their saved report) — newest first, for the Runs history."""
    with get_session() as s:
        rows = (s.query(RunResultRow)
                .order_by(RunResultRow.created_at.desc())
                .limit(limit).all())
        return {"runs": [
            {
                "run_id": r.id,
                "created_at": r.created_at.isoformat(),
                "target": r.target_base_url,
                "goal": r.goal,
                "verdict": r.verdict,
                "requests": r.requests,
                "error_rate": r.error_rate,
                "p95_ms": r.p95_ms,
                "rps": r.rps,
                "has_report": bool(r.report_json),
            }
            for r in rows
        ]}






class SlaProfileBody(BaseModel):
    name: str
    thresholds: list[dict]


@app.get("/api/sla", **doc("GET", "/api/sla"))
def list_sla() -> dict:
    """List saved SLA / threshold profiles."""
    with get_session() as s:
        rows = s.query(SlaProfileRow).order_by(SlaProfileRow.created_at.desc()).all()
        import json as _j
        return {"profiles": [
            {"id": r.id, "name": r.name, "thresholds": _j.loads(r.thresholds_json or "[]")}
            for r in rows
        ]}


@app.post("/api/sla", **doc("POST", "/api/sla"))
def create_sla(body: SlaProfileBody) -> dict:
    """Save a reusable SLA / threshold profile."""
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    import json as _j
    with get_session() as s:
        row = SlaProfileRow(name=body.name.strip(), thresholds_json=_j.dumps(body.thresholds))
        s.add(row)
        s.commit()
        return {"id": row.id, "name": row.name}


@app.delete("/api/sla/{sla_id}", **doc("DELETE", "/api/sla/{sla_id}"))
def delete_sla(sla_id: str) -> dict:
    with get_session() as s:
        row = s.get(SlaProfileRow, sla_id)
        if row is None:
            raise HTTPException(status_code=404, detail="not found")
        s.delete(row)
        s.commit()
        return {"deleted": sla_id}


@app.get("/api/runs/trend", **doc("GET", "/api/runs/trend"))
def runs_trend(plan_id: str = "", limit: int = 10) -> dict:
    """Return recent runs' key metrics for a plan (oldest->newest) for the trend chart."""
    with get_session() as s:
        q = s.query(RunResultRow)
        if plan_id:
            q = q.filter(RunResultRow.plan_id == plan_id)
        rows = q.order_by(RunResultRow.created_at.desc()).limit(limit).all()
        rows = list(reversed(rows))  # oldest first for a left-to-right chart
        return {"points": [
            {
                "created_at": r.created_at.isoformat(),
                "p95_ms": r.p95_ms,
                "error_rate": r.error_rate,
                "rps": r.rps,
                "verdict": r.verdict,
            }
            for r in rows
        ]}


@app.get("/api/runs/{result_id}/saved-report", **doc("GET", "/api/runs/{result_id}/saved-report"))
def get_saved_report(result_id: str) -> dict:
    """Return a previously-saved report so it can be reopened."""
    with get_session() as s:
        r = s.get(RunResultRow, result_id)
        if r is None or not r.report_json:
            raise HTTPException(status_code=404, detail="saved report not found")
        try:
            return json.loads(r.report_json)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail="corrupt saved report") from e




@app.post("/api/data", **doc("POST", "/api/data"))
async def upload_data(file: UploadFile) -> dict:
    """Upload a test-data file (CSV/TSV/TXT/JSON/JSONL). Parse + validate + store.

    Returns the detected columns and row count. The actual values are stored for the
    runner but never sent to the LLM — only the column names (schema) are used in
    planning.
    """
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="file must be UTF-8 text") from None

    filename = file.filename or "data.csv"
    try:
        dataset = load_data(filename, content)
    except DataValidationError as e:
        raise HTTPException(status_code=400, detail=f"invalid data file: {e}") from e

    with get_session() as s:
        row = DataFileRow(
            filename=filename,
            source_format=dataset.source_format,
            columns_csv=",".join(dataset.fields),
            row_count=dataset.row_count,
            content=content,
        )
        s.add(row)
        s.commit()
        data_id = row.id

    return {
        "data_file_id": data_id,
        "filename": filename,
        "fields": dataset.fields,
        "row_count": dataset.row_count,
        "source_format": dataset.source_format,
        "warnings": dataset.warnings,
        "sample_rows": dataset.rows[:_SAMPLE_ROWS],
    }


_SAMPLE_ROWS = 3      # rows shown back to the user so they can see what the file holds


def _data_rows(data_row) -> list[dict]:
    """The parsed rows of a stored data file ([] if it cannot be parsed)."""
    try:
        return load_data(data_row.filename, data_row.content).rows
    except Exception:  # noqa: BLE001
        return []


@app.get("/api/data/{data_file_id}", **doc("GET", "/api/data/{data_file_id}"))
def get_data_file(data_file_id: str) -> dict:
    """Columns, row count and first rows of a stored data file."""
    with get_session() as s:
        row = s.get(DataFileRow, data_file_id)
        if row is None:
            raise HTTPException(status_code=404, detail="data file not found")
        return {
            "data_file_id": row.id,
            "filename": row.filename,
            "fields": row.columns,
            "row_count": row.row_count,
            "source_format": row.source_format,
            "sample_rows": _data_rows(row)[:_SAMPLE_ROWS],
        }



@app.post("/api/import-endpoints", **doc("POST", "/api/import-endpoints"))
async def import_endpoints_api(file: UploadFile) -> dict:
    """Import endpoints from an OpenAPI/Swagger JSON, Postman collection, or HAR file."""
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="file must be UTF-8 text") from None
    try:
        result = import_endpoints(file.filename or "import.json", content)
    except ImportError_ as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result.to_dict()



@app.post("/api/plan", **doc("POST", "/api/plan"))
def create_plan(request: PlanRequest) -> dict:
    """AI drafts a LoadModel from the endpoints, saved; returns it for review."""
    try:
        provider = build_provider()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    tracing.set_step("plan")
    plan: PlanArtifact = draft_plan(request, provider)
    redaction_counts = getattr(provider, "last_redaction_counts", {}) or {}

    with get_session() as s:
        row = PlanRow(
            id=plan.id,
            target_base_url=plan.load_model.target_base_url,
            goal=request.goal,
            load_model_json=plan.load_model.model_dump_json(),
        )
        s.add(row)
        s.commit()

    _u = _usage_summary(provider)
    audit.record("plan.created", entity="plan", entity_id=plan.id,
                 target=plan.load_model.target_base_url,
                 summary=f"AI drafted a plan with {len(plan.load_model.scenarios)} scenario(s)",
                 tokens=_u.get("total_tokens", 0), cost_usd=_u.get("cost_usd", 0.0))

    # Grade the drafted plan against the endpoints that were actually supplied.
    plan_eval = evaluate_plan(plan.load_model, request).summary()

    return {
        "plan_id": plan.id,
        "provider": provider.name,
        "load_model": plan.load_model.model_dump(),
        "guardrail": _summarize_redactions(redaction_counts),
        "evaluation": plan_eval,
        "rationale": _plan_rationale(plan.load_model),
        "usage": _usage_summary(provider),
    }




class DynamizeBody(BaseModel):
    body: dict
    data_file_id: str | None = None


@app.post("/api/dynamize", **doc("POST", "/api/dynamize"))
def dynamize(req: DynamizeBody) -> dict:
    """Ask the AI to assign generator tokens to the fields of a body that should vary."""
    import json as _json
    if not req.body:
        raise HTTPException(status_code=400, detail="body is empty")
    try:
        provider = build_provider()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # look up the uploaded data file's columns, if one is attached
    columns: list[str] = []
    if req.data_file_id:
        with get_session() as s:
            dr = s.get(DataFileRow, req.data_file_id)
            if dr is not None:
                columns = dr.columns

    tracing.set_step("dynamize")
    result: DynamizedBody = provider.structured(
        response_model=DynamizedBody,
        system=DYNAMIZE_SYSTEM_PROMPT,
        user=build_dynamize_user_prompt(_json.dumps(req.body, indent=2), columns),
    )
    return {
        "body": result.body,
        "changed_fields": result.changed_fields,
        "notes": result.notes,
        "guardrail": _summarize_redactions(getattr(provider, "last_redaction_counts", {}) or {}),
        "usage": _usage_summary(provider),
    }




class SuggestChecksBody(BaseModel):
    sample_response: str


@app.post("/api/suggest-checks", **doc("POST", "/api/suggest-checks"))
def suggest_checks(body: SuggestChecksBody) -> dict:
    """Propose validation assertions from a pasted sample response (Option B).

    The response goes through the guarded provider (redacted) before the AI sees it.
    """
    if not body.sample_response.strip():
        raise HTTPException(status_code=400, detail="paste a sample response first")
    try:
        provider = build_provider()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    tracing.set_step("suggest_checks")
    result: SuggestedChecks = provider.structured(
        response_model=SuggestedChecks,
        system=CHECK_SUGGEST_SYSTEM_PROMPT,
        user=build_check_suggest_prompt(body.sample_response),
    )
    return {
        "checks": [c.model_dump() for c in result.checks],
        "notes": result.notes,
        "guardrail": _summarize_redactions(getattr(provider, "last_redaction_counts", {}) or {}),
        "usage": _usage_summary(provider),
    }

def _row_mode(value: str | None) -> str:
    if value not in ROW_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"data_row_mode must be one of: {', '.join(ROW_MODES)}")
    return value


def _attach_data_file(model: LoadModel, data_row, row_mode: str | None) -> DataFile:
    """The plan's data-file record for a stored file (values stay in the database).

    Keeps the row mode the plan already had unless a new one is given.
    """
    previous = model.data_file.row_mode if model.data_file else "random"
    return DataFile(
        filename=data_row.filename,
        fields=data_row.columns,
        row_count=data_row.row_count,
        source_format=data_row.source_format,
        row_mode=_row_mode(row_mode) if row_mode else previous,
    )


class LoadProfileBody(BaseModel):
    type: LoadProfileType = LoadProfileType.RAMP
    max_users: int = Field(gt=0, le=1_000_000)
    duration_seconds: int = Field(gt=0, le=7 * 24 * 3600)


@app.post("/api/load-profile", **doc("POST", "/api/load-profile"))
def load_profile(body: LoadProfileBody) -> dict:
    """Build the load stages for a test type, peak users and duration. No AI."""
    profile = build_profile(body.type, body.max_users, body.duration_seconds)
    return {
        "load_profile": profile.model_dump(mode="json"),
        "max_users": body.max_users,              # what was asked for
        "peak_users": profile.peak_users,         # the highest stage (stress goes past it)
        "total_seconds": profile.total_seconds,
    }


class RequestPreviewBody(BaseModel):
    load_model: LoadModel
    data_file_id: str | None = None
    data_row_mode: str | None = None
    samples: int = Field(default=3, ge=1, le=10)


@app.post("/api/request-preview", **doc("POST", "/api/request-preview"))
def request_preview(body: RequestPreviewBody) -> dict:
    """Show the first few requests of each step, filled with real rows and sample
    generated values. Sends nothing; no AI."""
    model = body.load_model
    rows: list[dict] = []
    if body.data_file_id:
        with get_session() as s:
            data_row = s.get(DataFileRow, body.data_file_id)
            if data_row is None:
                raise HTTPException(status_code=404, detail="data file not found")
            model.data_file = _attach_data_file(model, data_row, body.data_row_mode)
            rows = _data_rows(data_row)
    elif model.data_file is not None:
        # A plan reopened later: find its file by name, as the runner does.
        with get_session() as s:
            data_row = (s.query(DataFileRow)
                        .filter(DataFileRow.filename == model.data_file.filename)
                        .order_by(DataFileRow.created_at.desc()).first())
            rows = _data_rows(data_row) if data_row is not None else []
        if body.data_row_mode:
            model.data_file = model.data_file.model_copy(
                update={"row_mode": _row_mode(body.data_row_mode)})
    return preview_requests(model, rows, samples=body.samples)


@app.post("/api/plan/{plan_id}/generate", **doc("POST", "/api/plan/{plan_id}/generate"))
def generate(plan_id: str, body: GenerateBody) -> dict:
    """Render a plan to a script. Uses the edited LoadModel if provided, else stored.

    If a data_file_id is given, its schema is attached to the LoadModel so the
    generated script is parameterized from that data file.
    """
    with get_session() as s:
        row = s.get(PlanRow, plan_id)
        if row is None:
            raise HTTPException(status_code=404, detail="plan not found")

        model = body.load_model or LoadModel.model_validate_json(row.load_model_json)

        # Attach the uploaded data file's schema to the model (values stay in the DB).
        if body.data_file_id:
            data_row = s.get(DataFileRow, body.data_file_id)
            if data_row is None:
                raise HTTPException(status_code=404, detail="data file not found")
            model.data_file = _attach_data_file(model, data_row, body.data_row_mode)
        elif body.data_row_mode and model.data_file is not None:
            model.data_file = model.data_file.model_copy(
                update={"row_mode": _row_mode(body.data_row_mode)})

        # Attach custom headers (tokens/API keys) — go to the runner, not the LLM.
        if body.headers:
            model.headers = {k: v for k, v in body.headers.items() if k and v}

        # Persist the (possibly edited / data-attached) model.
        row.load_model_json = model.model_dump_json()
        row.target_base_url = model.target_base_url

        plan = PlanArtifact(id=plan_id, load_model=model)
        try:
            script = generate_script(plan, tool=body.tool)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        script_row = ScriptRow(
            id=script.id,
            plan_id=plan_id,
            tool=script.tool,
            filename=script.filename,
            content=script.content,
        )
        s.add(script_row)
        s.commit()

        audit.record("plan.approved", entity="plan", entity_id=plan_id,
                     target=model.target_base_url, summary="Plan approved by user")
        audit.record("script.generated", entity="script", entity_id=script.id,
                     target=model.target_base_url,
                     summary=f"Generated {script.tool} script {script.filename}")

        return {
            "script_id": script.id,
            "plan_id": plan_id,
            "tool": script.tool,
            "filename": script.filename,
            "content": script.content,
        }


@app.get("/api/plans", **doc("GET", "/api/plans"))
def list_plans() -> dict:
    with get_session() as s:
        rows = s.query(PlanRow).order_by(PlanRow.created_at.desc()).all()
        return {
            "plans": [
                {
                    "plan_id": r.id,
                    "target": r.target_base_url,
                    "goal": r.goal,
                    "created_at": r.created_at.isoformat(),
                    "script_count": len(r.scripts),
                }
                for r in rows
            ]
        }


@app.get("/api/plans/{plan_id}", **doc("GET", "/api/plans/{plan_id}"))
def get_plan(plan_id: str) -> dict:
    with get_session() as s:
        row = s.get(PlanRow, plan_id)
        if row is None:
            raise HTTPException(status_code=404, detail="plan not found")
        return {
            "plan_id": row.id,
            "target": row.target_base_url,
            "goal": row.goal,
            "load_model": LoadModel.model_validate_json(row.load_model_json).model_dump(),
            "scripts": [
                {
                    "script_id": sc.id,
                    "tool": sc.tool,
                    "filename": sc.filename,
                    "created_at": sc.created_at.isoformat(),
                }
                for sc in row.scripts
            ],
        }


@app.get("/api/scripts/{script_id}/download", response_class=PlainTextResponse, **doc("GET", "/api/scripts/{script_id}/download"))
def download_script(script_id: str) -> PlainTextResponse:
    with get_session() as s:
        row = s.get(ScriptRow, script_id)
        if row is None:
            raise HTTPException(status_code=404, detail="script not found")
        audit.record("script.downloaded", entity="script", entity_id=script_id,
                     summary=f"Downloaded {row.filename}")
        return PlainTextResponse(
            row.content,
            headers={"Content-Disposition": f'attachment; filename="{row.filename}"'},
        )



# ---------- pre-flight check ----------

class PreflightBody(BaseModel):
    load_model: LoadModel
    data_file_id: str | None = None
    headers: dict[str, str] | None = None


@app.post("/api/preflight", **doc("POST", "/api/preflight"))
def api_preflight(body: PreflightBody) -> dict:
    """Fire one request per endpoint and report status codes (no load)."""
    model = body.load_model
    if body.headers:
        model.headers = {k: v for k, v in body.headers.items() if k and v}

    sample_row = None
    if body.data_file_id:
        with get_session() as s:
            dr = s.get(DataFileRow, body.data_file_id)
            if dr is not None and dr.content:
                try:
                    from perfagent.data import load_data as _ld
                    ds = _ld(dr.filename, dr.content)
                    if ds.rows:
                        sample_row = ds.rows[0]
                except Exception:  # noqa: BLE001
                    sample_row = None

    try:
        return preflight(model, sample_row=sample_row)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"preflight failed: {e}") from e



@app.post("/api/scripts/{script_id}/validate", **doc("POST", "/api/scripts/{script_id}/validate"))
def api_validate_script(script_id: str) -> dict:
    """Smoke-test a generated script with 1 VU / 1 iteration before a full run."""
    with get_session() as s:
        row = s.get(ScriptRow, script_id)
        if row is None:
            raise HTTPException(status_code=404, detail="script not found")
        data_filename, data_content = "", ""
        plan = s.get(PlanRow, row.plan_id)
        if plan is not None:
            data_filename, data_content = _data_for_plan(s, plan)
        return validate_script(row.content, data_filename=data_filename,
                               data_content=data_content)



class UploadScriptBody(BaseModel):
    filename: str = "loadtest.js"
    content: str
    target_base_url: str = ""
    tool: str = "k6"


@app.post("/api/scripts/upload", **doc("POST", "/api/scripts/upload"))
def upload_script(body: UploadScriptBody) -> dict:
    """Store a hand-written / existing script and make it runnable, skipping planning.

    A minimal plan is saved alongside it (just the target URL) so the run, monitor and
    report path works exactly as for a generated script.
    """
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="script content is empty")
    tool = body.tool or "k6"
    if tool not in supported_tools():
        raise HTTPException(status_code=400, detail=f"unsupported tool {tool!r}")

    target = body.target_base_url.strip() or "http://127.0.0.1:8000"
    # a minimal LoadModel so the report/verdict path has something to read
    minimal = (
        '{"target_base_url":"' + target + '",'
        '"scenarios":[{"name":"uploaded","steps":[{"name":"request","path":"/"}]}],'
        '"load_profile":{"stages":[{"duration_seconds":1,"target_users":1}]},'
        '"thresholds":[{"metric":"error_rate","op":"<","value":0.05}]}'
    )
    with get_session() as s:
        plan_row = PlanRow(
            target_base_url=target,
            goal="Uploaded script (no AI plan)",
            load_model_json=minimal,
        )
        s.add(plan_row)
        s.commit()
        plan_id = plan_row.id

        script_row = ScriptRow(
            plan_id=plan_id,
            tool=tool,
            filename=body.filename or "loadtest.js",
            content=body.content,
        )
        s.add(script_row)
        s.commit()
        return {
            "script_id": script_row.id,
            "plan_id": plan_id,
            "tool": tool,
            "filename": script_row.filename,
            "content": body.content,
        }


# ---------- run + live monitor ----------

@app.get("/api/run/available", **doc("GET", "/api/run/available"))
def run_available() -> dict:
    """Tell the UI whether k6 is installed so it can show a helpful message."""
    return {"k6": k6_available()}


def _data_for_plan(session, plan_row) -> tuple[str, str]:
    """Return (filename, content) of the data file referenced by a plan, or ('','')."""
    try:
        model = LoadModel.model_validate_json(plan_row.load_model_json)
    except Exception:  # noqa: BLE001
        return "", ""
    if not model.data_file:
        return "", ""
    fname = model.data_file.filename
    # find the most recent uploaded data file with this filename
    dr = (
        session.query(DataFileRow)
        .filter(DataFileRow.filename == fname)
        .order_by(DataFileRow.created_at.desc())
        .first()
    )
    if dr is None:
        return "", ""
    return dr.filename, dr.content


@app.post("/api/scripts/{script_id}/run", **doc("POST", "/api/scripts/{script_id}/run"))
def run_script(script_id: str) -> dict:
    """Launch a script as a live run. Returns a run_id the UI polls for status."""
    with get_session() as s:
        row = s.get(ScriptRow, script_id)
        if row is None:
            raise HTTPException(status_code=404, detail="script not found")
        target = ""
        data_filename, data_content = "", ""
        plan = s.get(PlanRow, row.plan_id)
        if plan is not None:
            target = plan.target_base_url
            data_filename, data_content = _data_for_plan(s, plan)
        run_id = uuid.uuid4().hex
        run = start_run(
            run_id=run_id,
            script_id=script_id,
            tool=row.tool,
            target=target,
            content=row.content,
            load_model_json=(plan.load_model_json if plan is not None else ""),
            data_filename=data_filename,
            data_content=data_content,
        )
    peak = ""
    try:
        if plan is not None:
            from perfagent.contracts.load_model import LoadModel as _LM
            peak = _LM.model_validate_json(plan.load_model_json).load_profile.peak_users
    except Exception:  # noqa: BLE001
        peak = ""
    audit.record("run.started", entity="run", entity_id=run.run_id, target=target,
                 summary=f"Load run started against {target}"
                         + (f" (peak {peak} VUs)" if peak != "" else ""))
    return {"run_id": run.run_id, "status": run.status, "message": run.message}


@app.get("/api/runs/{run_id}", **doc("GET", "/api/runs/{run_id}"))
def run_status(run_id: str) -> dict:
    """Live status + aggregated metrics snapshot for a run."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run_id": run.run_id,
        "script_id": run.script_id,
        "tool": run.tool,
        "target": run.target,
        "status": run.status,
        "message": run.message,
        "elapsed_s": round((run.ended_at or time.time()) - run.started_at, 1),
        "snapshot": run.snapshot,
        "logs": list(getattr(run, "logs", []) or [])[-200:],   # recent k6 output lines
    }


@app.post("/api/runs/{run_id}/stop", **doc("POST", "/api/runs/{run_id}/stop"))
def run_stop(run_id: str) -> dict:
    ok = stop_run(run_id)
    if not ok:
        raise HTTPException(status_code=400, detail="run not running")
    return {"run_id": run_id, "status": "stopped"}


# ---------- analyze + report ----------

def _build_report(run) -> tuple[dict, str]:
    """Compute verdict, narrate, and render HTML for a finished run. Returns (verdict, html)."""
    from perfagent.analyzer import evaluate, narrate, render_report_html

    if run.load_model_json:
        model = LoadModel.model_validate_json(run.load_model_json)
    else:
        model = LoadModel.model_validate_json(
            '{"target_base_url":"' + (run.target or "http://unknown")
            + '","scenarios":[{"name":"s","steps":[{"name":"x","path":"/"}]}],'
            '"load_profile":{"stages":[{"duration_seconds":1,"target_users":1}]},'
            '"thresholds":[]}'
        )

    verdict = evaluate(model, run.snapshot)

    try:
        provider = build_provider()
    except ValueError:
        provider = None
    tracing.set_step('narrate')
    narrative = narrate(run.target, run.snapshot, verdict, provider)

    report_html = render_report_html(
        target=run.target,
        tool=run.tool,
        snapshot=run.snapshot,
        verdict=verdict,
        narrative=narrative,
        plan_id="",
        run_id=run.run_id,
    )
    return verdict, report_html


@app.get("/api/runs/{run_id}/report", **doc("GET", "/api/runs/{run_id}/report"))
def run_report(run_id: str) -> dict:
    """Return the verdict + narrative for a finished run (for the UI panel)."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status not in ("finished", "stopped", "error"):
        raise HTTPException(status_code=400, detail="run has not finished yet")

    from perfagent.analyzer import evaluate, narrate

    if run.load_model_json:
        model = LoadModel.model_validate_json(run.load_model_json)
    else:
        model = None

    verdict = evaluate(model, run.snapshot) if model else {"overall_passed": None, "checks": []}
    try:
        provider = build_provider()
    except ValueError:
        provider = None
    tracing.set_step('narrate')
    narrative = narrate(run.target, run.snapshot, verdict, provider)

    # Check the AI narrative cites only real, computed numbers.
    narrative_text = " ".join([
        narrative.headline, narrative.summary,
        " ".join(narrative.observations), " ".join(narrative.recommendations),
    ])
    report_eval = evaluate_report(narrative_text, run.snapshot, verdict).summary()

    # Deterministic diagnostics — bottlenecks, tails, concurrency impact.
    peak = None
    if model is not None:
        try:
            peak = model.load_profile.peak_users
        except Exception:  # noqa: BLE001
            peak = None
    diag = diagnose(run.snapshot, peak_users=peak)

    # ----- baseline / regression: compare to the previous run of this plan -----
    cur_metrics = metrics_from_snapshot(run.snapshot)
    plan_id = ""
    with get_session() as s:
        sc = s.get(ScriptRow, run.script_id)
        if sc is not None:
            plan_id = sc.plan_id
        baseline_summary = no_baseline()
        if plan_id:
            prev = (
                s.query(RunResultRow)
                .filter(RunResultRow.plan_id == plan_id)
                .order_by(RunResultRow.created_at.desc())
                .first()
            )
            if prev is not None:
                baseline_summary = compare(cur_metrics, {
                    "error_rate": prev.error_rate, "p95_ms": prev.p95_ms,
                    "p99_ms": prev.p99_ms, "avg_ms": prev.avg_ms, "rps": prev.rps,
                })
            # store THIS run as the new latest result for the plan
            vtxt = ("pass" if verdict.get("overall_passed") is True
                    else "fail" if verdict.get("overall_passed") is False
                    else "inconclusive")
            audit.record("run.finished", entity="run", entity_id=run.run_id,
                         target=run.target,
                         summary=f"Run {vtxt.upper()} — {cur_metrics['requests']} requests, "
                                 f"{cur_metrics['error_rate']*100:.2f}% errors")
            # Full report payload — persisted so it can be reopened later.
            report_payload = {
                "run_id": run.run_id,
                "target": run.target,
                "verdict": verdict,
                "narrative": narrative.model_dump(),
                "evaluation": report_eval,
                "diagnostics": diag.to_dict(),
                "baseline": baseline_summary,
                "snapshot": run.snapshot,
                "logs": list(getattr(run, "logs", []) or []),   # persisted run logs
            }
            goal = ""
            prow = s.get(PlanRow, plan_id)
            if prow is not None:
                goal = prow.goal or ""
            s.add(RunResultRow(
                plan_id=plan_id, target_base_url=run.target, verdict=vtxt,
                requests=cur_metrics["requests"], error_rate=cur_metrics["error_rate"],
                rps=cur_metrics["rps"], p95_ms=cur_metrics["p95_ms"],
                p99_ms=cur_metrics["p99_ms"], avg_ms=cur_metrics["avg_ms"],
                goal=goal, report_json=json.dumps(report_payload),
            ))
            s.commit()

    return {
        "run_id": run.run_id,
        "target": run.target,
        "verdict": verdict,
        "narrative": narrative.model_dump(),
        "evaluation": report_eval,
        "diagnostics": diag.to_dict(),
        "baseline": baseline_summary,
        "logs": list(getattr(run, "logs", []) or [])[-500:],
    }


@app.get("/api/runs/{run_id}/logs/download", **doc("GET", "/api/runs/{run_id}/logs/download"))
def run_logs_download(run_id: str):
    """Download the run's logs as a .txt file (live run, or from the saved report)."""
    from fastapi.responses import PlainTextResponse
    run = get_run(run_id)
    lines: list[str] = []
    if run is not None and getattr(run, "logs", None):
        lines = list(run.logs)
    else:
        # fall back to the saved report's logs
        with get_session() as s:
            r = s.get(RunResultRow, run_id)
            if r is not None and r.report_json:
                try:
                    lines = json.loads(r.report_json).get("logs", []) or []
                except Exception:  # noqa: BLE001
                    lines = []
    if not lines:
        raise HTTPException(status_code=404, detail="no logs for this run")
    body = "\n".join(lines)
    return PlainTextResponse(
        body, headers={"Content-Disposition": f'attachment; filename="run_{run_id}_logs.txt"'})


@app.get("/api/runs/{run_id}/report/download", response_class=HTMLResponse, **doc("GET", "/api/runs/{run_id}/report/download"))
def run_report_download(run_id: str) -> HTMLResponse:
    """Download the full HTML report."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    _, report_html = _build_report(run)
    return HTMLResponse(
        report_html,
        headers={"Content-Disposition": f'attachment; filename="report_{run_id[:8]}.html"'},
    )