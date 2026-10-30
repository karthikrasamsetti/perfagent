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

Start with:  uv run uvicorn perfagent.api.app:app --reload
Then open:   http://127.0.0.1:8080
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from perfagent.contracts.artifacts import PlanArtifact
from perfagent.contracts.load_model import DataFile, LoadModel
from perfagent.data import DataValidationError, load_data
from perfagent.analyzer.diagnostics import diagnose
from perfagent.preflight import preflight
from perfagent.runner.validator import validate_script
from perfagent.importers import ImportError_, import_endpoints
from perfagent.db import DataFileRow, PlanRow, ScriptRow, get_session
from perfagent.evaluation import evaluate_plan, evaluate_report
from perfagent.generator import generate_script, supported_tools
from perfagent.planner import PlanRequest, draft_plan
from perfagent.providers import build_provider
from perfagent.runner import get_run, k6_available, start_run, stop_run

app = FastAPI(title="AI Performance Testing Agent")

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"


# ---------- request/response models ----------

class GenerateBody(BaseModel):
    tool: str = "k6"
    # Optional: the (possibly human-edited) LoadModel to use instead of the stored one.
    load_model: LoadModel | None = None
    # Optional: id of an uploaded data file to attach to this plan for the run.
    data_file_id: str | None = None
    # Optional: global headers to apply to every request (e.g. Authorization).
    headers: dict[str, str] | None = None


# ---------- guardrail reporting ----------

_REDACTION_LABELS = {
    "EMAIL": "email",
    "JWT": "auth token",
    "APIKEY": "API key",
    "CARD": "card number",
    "SSN": "SSN",
    "HOST": "internal host",
    "PRIVATE_IP": "private IP",
    "INLINE_SECRET": "secret",
    "FIELD": "secret field",
    "URL_HOST": "URL host",
    "QUERY_SECRET": "URL secret",
}


def _summarize_redactions(counts: dict) -> dict:
    """Turn raw redaction counts into a UI-friendly summary. No raw values, ever."""
    total = sum(counts.values()) if counts else 0
    parts = []
    for key, n in sorted(counts.items()):
        label = _REDACTION_LABELS.get(key, key.lower())
        parts.append(f"{n} {label}{'s' if n != 1 else ''}")
    return {"total": total, "detail": ", ".join(parts)}


# ---------- UI ----------

@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (_WEB_DIR / "index.html").read_text(encoding="utf-8")


# ---------- API ----------

@app.get("/api/tools")
def tools() -> dict:
    return {"tools": supported_tools()}


@app.post("/api/data")
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
    }



@app.post("/api/import-endpoints")
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



def _plan_rationale(model) -> str:
    """A short, always-accurate explanation of the plan's main choices."""
    scs = model.scenarios or []
    if not scs:
        return ""
    weights = model.normalised_weights()
    # the heaviest journey
    top_i = max(range(len(scs)), key=lambda i: weights[i])
    top = scs[top_i]
    bits = []
    bits.append(
        f"'{top.name}' is weighted highest ({round(weights[top_i]*100)}%) because it's "
        f"treated as the most common user action"
    )
    # correlation note
    has_auth = any(k.lower() == "authorization" for k in (model.headers or {}))
    if has_auth:
        bits.append("the journey logs in first and reuses the token on protected steps")
    # profile note
    bits.append(
        f"load ramps up, holds, then ramps down over {model.load_profile.total_seconds}s "
        "so the system is tested gradually rather than all at once"
    )
    return "; ".join(bits) + "."


@app.post("/api/plan")
def create_plan(request: PlanRequest) -> dict:
    """AI drafts a LoadModel from the endpoints, saved; returns it for review."""
    try:
        provider = build_provider()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

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

    # Grade the drafted plan against the endpoints that were actually supplied.
    plan_eval = evaluate_plan(plan.load_model, request).summary()

    return {
        "plan_id": plan.id,
        "provider": provider.name,
        "load_model": plan.load_model.model_dump(),
        "guardrail": _summarize_redactions(redaction_counts),
        "evaluation": plan_eval,
        "rationale": _plan_rationale(plan.load_model),
    }


@app.post("/api/plan/{plan_id}/generate")
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
            model.data_file = DataFile(
                filename=data_row.filename,
                fields=data_row.columns,
                row_count=data_row.row_count,
                source_format=data_row.source_format,
            )

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

        return {
            "script_id": script.id,
            "plan_id": plan_id,
            "tool": script.tool,
            "filename": script.filename,
            "content": script.content,
        }


@app.get("/api/plans")
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


@app.get("/api/plans/{plan_id}")
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


@app.get("/api/scripts/{script_id}/download", response_class=PlainTextResponse)
def download_script(script_id: str) -> PlainTextResponse:
    with get_session() as s:
        row = s.get(ScriptRow, script_id)
        if row is None:
            raise HTTPException(status_code=404, detail="script not found")
        return PlainTextResponse(
            row.content,
            headers={"Content-Disposition": f'attachment; filename="{row.filename}"'},
        )



# ---------- pre-flight check ----------

class PreflightBody(BaseModel):
    load_model: LoadModel
    data_file_id: str | None = None
    headers: dict[str, str] | None = None


@app.post("/api/preflight")
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



@app.post("/api/scripts/{script_id}/validate")
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


@app.post("/api/scripts/upload")
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

@app.get("/api/run/available")
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


@app.post("/api/scripts/{script_id}/run")
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
    return {"run_id": run.run_id, "status": run.status, "message": run.message}


@app.get("/api/runs/{run_id}")
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
    }


@app.post("/api/runs/{run_id}/stop")
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


@app.get("/api/runs/{run_id}/report")
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

    return {
        "run_id": run.run_id,
        "target": run.target,
        "verdict": verdict,
        "narrative": narrative.model_dump(),
        "evaluation": report_eval,
        "diagnostics": diag.to_dict(),
    }


@app.get("/api/runs/{run_id}/report/download", response_class=HTMLResponse)
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