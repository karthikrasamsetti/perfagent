"""API routes: run PerfAgent tests in Jenkins and follow the build.

  POST /api/jenkins/trigger    start the job with TEST / PERF_ENV        -> queue id
  POST /api/jenkins/status     queued/running/finished + console + results
  POST /api/jenkins/stop       abort a running build
  POST /api/jenkins/setup-job  create or update the Pipeline job for a framework

The browser sends the Jenkins URL, user and API token with every call; PerfAgent
keeps nothing between calls (no stored credentials, no background polling).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, SecretStr

from perfagent import audit, integrations
from perfagent.api.docs import doc
from perfagent.ci.jenkins import (
    JenkinsClient,
    JenkinsError,
    JenkinsTarget,
    build_status,
    console_chunk,
    k6_results,
    queue_status,
    setup_job,
    stop_build,
    trigger,
    validate,
)
from perfagent.config import get_settings

router = APIRouter()


class JenkinsAuth(BaseModel):
    # Optional fields checked in code, so a 422 can never echo the token back.
    jenkins_url: str = ""
    username: str = ""
    api_token: SecretStr | None = None
    job: str = ""
    # The plan the user is working on, so the details can be remembered for it.
    plan_id: str | None = None


class TriggerBody(JenkinsAuth):
    test: str = "all"
    environment: str = "dev"


class StatusBody(JenkinsAuth):
    queue_id: int | None = None
    build_number: int | None = None
    log_start: int = 0
    include_results: bool = True


class StopBody(JenkinsAuth):
    build_number: int = 0


class SetupBody(JenkinsAuth):
    repo_url: str = ""
    branch: str = "main"
    framework: str = ""
    git_credentials_id: str = ""


def _client(body: JenkinsAuth) -> tuple[JenkinsClient, list[str]]:
    st = get_settings()
    target = JenkinsTarget(
        url=body.jenkins_url.strip(),
        username=body.username.strip(),
        api_token=body.api_token.get_secret_value() if body.api_token else "",
        job=body.job.strip(),
        allowed_hosts=st.jenkins_allowed_hosts.split(","),
    )
    try:
        warnings = validate(target)
    except JenkinsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return JenkinsClient(target), warnings


def _call(fn):
    try:
        return fn()
    except JenkinsError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/api/jenkins/settings", **doc("GET", "/api/jenkins/settings"))
def jenkins_settings() -> dict:
    hosts = [h.strip() for h in get_settings().jenkins_allowed_hosts.split(",") if h.strip()]
    return {"allowed_hosts": hosts}


@router.post("/api/jenkins/trigger", **doc("POST", "/api/jenkins/trigger"))
def jenkins_trigger(body: TriggerBody) -> dict:
    client, warnings = _client(body)
    params = {"TEST": (body.test or "all").strip(), "PERF_ENV": (body.environment or "dev").strip()}
    try:
        queue_id = trigger(client, params)
    except JenkinsError as e:
        code = 400 if "invalid value" in str(e) else 502
        raise HTTPException(status_code=code, detail=str(e)) from e
    integrations.save(body.plan_id, jenkins={
        "url": client.t.url, "username": client.t.username, "job": client.t.job,
        "test": params["TEST"], "environment": params["PERF_ENV"]})
    audit.record("jenkins.triggered", entity="jenkins", entity_id=str(queue_id),
                 target=client.t.url,
                 summary=f"Job '{client.t.job}' TEST={params['TEST']} PERF_ENV={params['PERF_ENV']}")
    return {"queue_id": queue_id, "job": client.t.job, "warnings": warnings}


@router.post("/api/jenkins/status", **doc("POST", "/api/jenkins/status"))
def jenkins_status(body: StatusBody) -> dict:
    client, _w = _client(body)

    def run():
        if body.build_number:
            st = build_status(client, body.build_number)
        elif body.queue_id is not None:
            st = queue_status(client, body.queue_id)
            if st.number:
                st = build_status(client, st.number)
        else:
            raise JenkinsError("no queue id or build number given")

        out = {"state": st.state, "why": st.why, "build_number": st.number, "build_url": st.url,
               "result": st.result, "duration_ms": st.duration_ms,
               "log": "", "log_next": body.log_start, "log_more": False, "results": None,
               "verdict": None}
        if st.number:
            text, nxt, more = console_chunk(client, st.number, body.log_start)
            out.update(log=text, log_next=nxt, log_more=more)
        # Results + audit only once the whole console log has been delivered, so the
        # final poll is the only one that reports (and records) the outcome.
        if st.state == "finished" and not out["log_more"] and body.include_results and st.number:
            out["results"] = k6_results(client, st.number)
            verdicts = [r["verdict"] for r in out["results"]]
            out["verdict"] = ("fail" if "fail" in verdicts else "pass" if verdicts and
                              all(v == "pass" for v in verdicts) else
                              "inconclusive" if verdicts else None)
            audit.record("jenkins.finished", entity="jenkins", entity_id=str(st.number),
                         target=client.t.url,
                         summary=f"Job '{client.t.job}' #{st.number}: {st.result}"
                                 + (f", verdict {out['verdict']}" if out.get("verdict") else ""))
        return out

    return _call(run)


@router.post("/api/jenkins/stop", **doc("POST", "/api/jenkins/stop"))
def jenkins_stop(body: StopBody) -> dict:
    client, _w = _client(body)
    if body.build_number <= 0:
        raise HTTPException(status_code=400, detail="no build to stop")
    _call(lambda: stop_build(client, body.build_number))
    audit.record("jenkins.stopped", entity="jenkins", entity_id=str(body.build_number),
                 target=client.t.url, summary=f"Job '{client.t.job}' #{body.build_number} stopped")
    return {"stopped": True}


@router.post("/api/jenkins/setup-job", **doc("POST", "/api/jenkins/setup-job"))
def jenkins_setup_job(body: SetupBody) -> dict:
    client, warnings = _client(body)
    try:
        action = setup_job(client, repo_url=body.repo_url.strip(), branch=body.branch.strip() or "main",
                           framework=body.framework.strip(),
                           git_credentials_id=body.git_credentials_id.strip())
    except JenkinsError as e:
        code = 400 if str(e).startswith(("enter", "invalid")) else 502
        raise HTTPException(status_code=code, detail=str(e)) from e
    integrations.save(body.plan_id, jenkins={
        "url": client.t.url, "username": client.t.username, "job": client.t.job,
        "repo_url": body.repo_url, "branch": body.branch, "framework": body.framework,
        "git_credentials_id": body.git_credentials_id})
    audit.record("jenkins.job_configured", entity="jenkins", entity_id=client.t.job[:32],
                 target=client.t.url,
                 summary=f"Job '{client.t.job}' {action} for {body.framework} ({body.branch})")
    return {"action": action, "job": client.t.job, "warnings": warnings}