"""FastAPI service — the agent's API plus the web UI.

Endpoints:
  GET  /                      -> the web UI (HTML)
  GET  /api/tools            -> supported tools (k6 first)
  POST /api/plan             -> AI drafts a LoadModel, saved; returns it for review
  POST /api/plan/{id}/generate  -> render a saved (possibly edited) plan to a script
  GET  /api/plans            -> list saved plans
  GET  /api/plans/{id}       -> one plan + its scripts (lineage)
  GET  /api/scripts/{id}/download -> download a script file

Start with:  uv run uvicorn perfagent.api.app:app --reload
Then open:   http://127.0.0.1:8080
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from perfagent.contracts.artifacts import PlanArtifact
from perfagent.contracts.load_model import LoadModel
from perfagent.db import PlanRow, ScriptRow, get_session
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


# ---------- UI ----------

@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (_WEB_DIR / "index.html").read_text(encoding="utf-8")


# ---------- API ----------

@app.get("/api/tools")
def tools() -> dict:
    return {"tools": supported_tools()}


@app.post("/api/plan")
def create_plan(request: PlanRequest) -> dict:
    """AI drafts a LoadModel from the endpoints, saves it, returns it for review."""
    try:
        provider = build_provider()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    plan: PlanArtifact = draft_plan(request, provider)

    with get_session() as s:
        row = PlanRow(
            id=plan.id,
            target_base_url=plan.load_model.target_base_url,
            goal=request.goal,
            load_model_json=plan.load_model.model_dump_json(),
        )
        s.add(row)
        s.commit()

    return {
        "plan_id": plan.id,
        "provider": provider.name,
        "load_model": plan.load_model.model_dump(),
    }


@app.post("/api/plan/{plan_id}/generate")
def generate(plan_id: str, body: GenerateBody) -> dict:
    """Render a plan to a script. Uses the edited LoadModel if provided, else stored."""
    with get_session() as s:
        row = s.get(PlanRow, plan_id)
        if row is None:
            raise HTTPException(status_code=404, detail="plan not found")

        model = body.load_model or LoadModel.model_validate_json(row.load_model_json)
        # If the human edited the plan, persist the new version.
        if body.load_model is not None:
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


# ---------- run + live monitor ----------

@app.get("/api/run/available")
def run_available() -> dict:
    """Tell the UI whether k6 is installed so it can show a helpful message."""
    return {"k6": k6_available()}


@app.post("/api/scripts/{script_id}/run")
def run_script(script_id: str) -> dict:
    """Launch a script as a live run. Returns a run_id the UI polls for status."""
    with get_session() as s:
        row = s.get(ScriptRow, script_id)
        if row is None:
            raise HTTPException(status_code=404, detail="script not found")
        target = ""
        plan = s.get(PlanRow, row.plan_id)
        if plan is not None:
            target = plan.target_base_url
        run_id = uuid.uuid4().hex
        run = start_run(
            run_id=run_id,
            script_id=script_id,
            tool=row.tool,
            target=target,
            content=row.content,
            load_model_json=(plan.load_model_json if plan is not None else ""),
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
        "elapsed_s": round((run.ended_at or __import__("time").time()) - run.started_at, 1),
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
        # minimal empty-threshold model so evaluation still runs
        model = LoadModel.model_validate_json(
            '{"target_base_url":"' + (run.target or "http://unknown")
            + '","scenarios":[{"name":"s","steps":[{"name":"x","path":"/"}]}],'
            '"load_profile":{"stages":[{"duration_seconds":1,"target_users":1}]},'
            '"thresholds":[]}'
        )

    verdict = evaluate(model, run.snapshot)

    # narration uses the LLM if configured, else a deterministic fallback
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

    return {
        "run_id": run.run_id,
        "target": run.target,
        "verdict": verdict,
        "narrative": narrative.model_dump(),
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