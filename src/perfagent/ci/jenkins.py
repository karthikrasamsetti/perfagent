"""Trigger and follow Jenkins pipelines from PerfAgent (Jenkins REST API).

Jenkins runs the framework that "Save to Git" committed (<framework>/ci/Jenkinsfile),
so the job builds the version of the test that is in Git.

Calls used:
  POST {job}/buildWithParameters?TEST=..&PERF_ENV=..   start a build  -> queue item
  GET  /queue/item/{id}/api/json                        queued -> build number
  GET  {job}/{n}/api/json                               building / result
  GET  {job}/{n}/logText/progressiveText?start=N        console log, incrementally
  GET  {job}/{n}/artifact/<path>                        k6 summary JSON the Jenkinsfile archived
  POST {job}/{n}/stop                                   abort
  POST {folder}/createItem?name=..  /  {job}/config.xml create or update the job

Credentials: Jenkins user name + API token, sent as HTTP Basic auth. With an API
token Jenkins doesn't need a CSRF crumb; if a server still asks for one, it is fetched
and the request retried once. The token is only held for the duration of one call and
is scrubbed from any error text. Only the standard library is used (urllib), so corporate
proxies set through HTTPS_PROXY / HTTP_PROXY are honoured.
"""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

# Jenkins embeds hidden console annotations (ESC[8mha:////<base64>ESC[0m) and ANSI
# colours in the raw log; they are noise outside Jenkins' own page.
_CONSOLE_NOTE = re.compile(r"\x1b\[8mha:[^\x1b]*\x1b\[0m")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_JOB_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,127}$")
_PARAM_OK = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_TIMEOUT = 30
MAX_LOG_CHUNK = 200_000
MAX_ARTIFACT_BYTES = 5_000_000


class JenkinsError(RuntimeError):
    """A clean, user-facing Jenkins problem (no secrets inside)."""


@dataclass
class JenkinsTarget:
    url: str                       # e.g. https://jenkins.mycorp.com  (may include a /jenkins prefix)
    username: str
    api_token: str
    job: str                       # job name; folders with '/', e.g. "perf/demo-perf"
    allowed_hosts: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ validation / paths

def validate(t: JenkinsTarget) -> list[str]:
    """Check the target; returns warnings (e.g. plain http). Raises JenkinsError."""
    warnings: list[str] = []
    url = (t.url or "").strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise JenkinsError("enter the Jenkins URL, e.g. https://jenkins.mycompany.com")
    if parsed.username or parsed.password:
        raise JenkinsError("put the API token in the API token field, not inside the Jenkins URL")
    if parsed.query or parsed.fragment:
        raise JenkinsError("the Jenkins URL must not contain ? or #")
    if parsed.scheme == "http":
        warnings.append("Jenkins is reached over plain http, so the API token is not encrypted in transit.")
    allowed = [h.strip().lower() for h in t.allowed_hosts if h.strip()]
    if allowed and parsed.hostname.lower() not in allowed:
        raise JenkinsError(f"Jenkins host {parsed.hostname!r} is not in the allowed list ({', '.join(allowed)})")
    if not (t.username or "").strip() or not (t.api_token or "").strip():
        raise JenkinsError("enter your Jenkins user name and API token")
    job_segments(t.job)
    return warnings


def job_segments(job: str) -> list[str]:
    parts = [p.strip() for p in (job or "").strip().strip("/").split("/")]
    if not parts or not all(_JOB_SEGMENT.match(p) for p in parts):
        raise JenkinsError("enter a valid Jenkins job name (use '/' for folders, e.g. perf/demo-perf)")
    return parts


def _job_path(job: str) -> str:
    return "".join(f"/job/{urllib.parse.quote(p, safe='')}" for p in job_segments(job))


def _base(t: JenkinsTarget) -> str:
    return t.url.strip().rstrip("/")


# ------------------------------------------------------------------ HTTP

@dataclass
class _Resp:
    status: int
    body: bytes
    headers: dict[str, str]


class JenkinsClient:
    def __init__(self, target: JenkinsTarget):
        self.t = target
        basic = base64.b64encode(f"{target.username.strip()}:{target.api_token.strip()}".encode()).decode()
        self._auth = f"Basic {basic}"
        self._secrets = [s for s in (target.api_token.strip(), basic) if s]
        self._crumb: tuple[str, str] | None = None

    def _scrub(self, text: str) -> str:
        for s in self._secrets:
            text = text.replace(s, "***")
        return text

    def _send(self, method: str, path: str, data: bytes | None = None,
              content_type: str | None = None, max_bytes: int = MAX_ARTIFACT_BYTES) -> _Resp:
        url = _base(self.t) + path
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", self._auth)
        req.add_header("Accept", "application/json, text/plain, */*")
        if content_type:
            req.add_header("Content-Type", content_type)
        if self._crumb and method != "GET":
            req.add_header(*self._crumb)
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=_TIMEOUT) as r:
                body = r.read(max_bytes + 1)
                return _Resp(r.status, body[:max_bytes], {k.lower(): v for k, v in r.headers.items()})
        except urllib.error.HTTPError as e:
            body = e.read(20_000) if e.fp else b""
            return _Resp(e.code, body, {k.lower(): v for k, v in (e.headers or {}).items()})
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise JenkinsError(self._scrub(f"could not reach Jenkins at {_base(self.t)}: {reason}")) from None

    def request(self, method: str, path: str, data: bytes | None = None,
                content_type: str | None = None, max_bytes: int = MAX_ARTIFACT_BYTES) -> _Resp:
        r = self._send(method, path, data, content_type, max_bytes)
        if r.status == 403 and method != "GET" and b"crumb" in r.body.lower() and not self._crumb:
            self._fetch_crumb()
            r = self._send(method, path, data, content_type, max_bytes)
        if r.status == 401:
            raise JenkinsError("Jenkins rejected the user name or API token")
        if r.status == 403:
            raise JenkinsError("this Jenkins user isn't allowed to do that (check the job's permissions)")
        return r

    def _fetch_crumb(self) -> None:
        r = self._send("GET", "/crumbIssuer/api/json")
        if r.status == 200:
            try:
                j = json.loads(r.body)
                self._crumb = (j["crumbRequestField"], j["crumb"])
            except (ValueError, KeyError):
                pass

    def get_json(self, path: str) -> dict:
        r = self.request("GET", path)
        if r.status == 404:
            raise JenkinsError("not found in Jenkins (check the job name and that the job exists)")
        if r.status >= 400:
            raise JenkinsError(f"Jenkins returned HTTP {r.status}")
        try:
            return json.loads(r.body or b"{}")
        except ValueError:
            raise JenkinsError("Jenkins sent an unexpected (non-JSON) reply — check the Jenkins URL") from None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Don't follow redirects (they would re-send credentials to wherever Jenkins points)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


# ------------------------------------------------------------------ operations

def trigger(client: JenkinsClient, params: dict[str, str]) -> int:
    """Start a build with parameters. Returns the queue item id."""
    for k, v in params.items():
        if not _PARAM_OK.match(k) or not _PARAM_OK.match(v or ""):
            raise JenkinsError(f"invalid value for {k}: use letters, numbers, '-', '_' or '.'")
    path = _job_path(client.t.job) + "/buildWithParameters"
    body = urllib.parse.urlencode(params).encode()
    r = client.request("POST", path, body, "application/x-www-form-urlencoded")
    if r.status == 404:
        raise JenkinsError(f"job '{client.t.job}' was not found in Jenkins — create it, or use 'Set up Jenkins job'")
    if r.status in (400, 500) and b"parameter" in r.body.lower():
        raise JenkinsError(
            f"job '{client.t.job}' doesn't accept parameters yet. Jenkins learns a pipeline's parameters "
            "after its first build: run it once in Jenkins, or use 'Set up Jenkins job'."
        )
    if r.status not in (200, 201):
        raise JenkinsError(f"Jenkins refused to start the build (HTTP {r.status})")
    m = re.search(r"/queue/item/(\d+)", r.headers.get("location", ""))
    if not m:
        raise JenkinsError("Jenkins accepted the request but didn't return a queue item")
    return int(m.group(1))


@dataclass
class BuildStatus:
    state: str                     # queued | running | finished | cancelled
    why: str = ""                  # why it's still queued
    number: int | None = None
    url: str = ""
    result: str | None = None      # SUCCESS | FAILURE | UNSTABLE | ABORTED | NOT_BUILT
    duration_ms: int = 0


def queue_status(client: JenkinsClient, queue_id: int) -> BuildStatus:
    try:
        j = client.get_json(f"/queue/item/{int(queue_id)}/api/json")
    except JenkinsError as e:
        if "not found" in str(e):
            # Jenkins forgets queue items a few minutes after the build starts.
            raise JenkinsError("Jenkins no longer knows this queue item; open the job in Jenkins to see the build") from None
        raise
    if j.get("cancelled"):
        return BuildStatus(state="cancelled", why="the build was cancelled while queued")
    exe = j.get("executable") or {}
    if exe.get("number"):
        return BuildStatus(state="running", number=int(exe["number"]), url=str(exe.get("url", "")))
    return BuildStatus(state="queued", why=str(j.get("why") or "waiting for an executor"))


def build_status(client: JenkinsClient, number: int) -> BuildStatus:
    j = client.get_json(f"{_job_path(client.t.job)}/{int(number)}/api/json"
                        "?tree=building,result,duration,url,number")
    building = bool(j.get("building"))
    return BuildStatus(state="running" if building else "finished", number=int(number),
                       url=str(j.get("url", "")), result=j.get("result"),
                       duration_ms=int(j.get("duration") or 0))


def console_chunk(client: JenkinsClient, number: int, start: int) -> tuple[str, int, bool]:
    """Return (text, next_start, more_data) from the build's console log."""
    r = client.request("GET", f"{_job_path(client.t.job)}/{int(number)}/logText/progressiveText"
                              f"?start={max(0, int(start))}", max_bytes=MAX_LOG_CHUNK)
    if r.status >= 400:
        return "", start, False
    text = r.body.decode("utf-8", errors="replace")
    try:
        nxt = int(r.headers.get("x-text-size", start + len(r.body)))
    except ValueError:
        nxt = start + len(r.body)
    text = _ANSI.sub("", _CONSOLE_NOTE.sub("", text))
    return client._scrub(text), nxt, r.headers.get("x-more-data", "").lower() == "true"


def stop_build(client: JenkinsClient, number: int) -> None:
    r = client.request("POST", f"{_job_path(client.t.job)}/{int(number)}/stop")
    if r.status not in (200, 201, 302):
        raise JenkinsError(f"Jenkins couldn't stop build #{number} (HTTP {r.status})")


# ------------------------------------------------------------------ results

def k6_results(client: JenkinsClient, number: int) -> list[dict]:
    """Read the k6 summaries the Jenkinsfile archived (results/<test>-summary.json)."""
    j = client.get_json(f"{_job_path(client.t.job)}/{int(number)}/api/json"
                        "?tree=artifacts[relativePath,fileName]")
    out = []
    for art in j.get("artifacts") or []:
        rel = str(art.get("relativePath", ""))
        name = str(art.get("fileName", ""))
        if not name.endswith("-summary.json") or ".." in rel:
            continue
        path = f"{_job_path(client.t.job)}/{int(number)}/artifact/" + urllib.parse.quote(rel)
        r = client.request("GET", path)
        if r.status != 200:
            continue
        try:
            out.append({"test": name[: -len("-summary.json")], **summarize_k6(json.loads(r.body))})
        except (ValueError, TypeError, AttributeError):
            continue
    return out


def summarize_k6(summary: dict) -> dict:
    """Turn a k6 --summary-export file into PerfAgent's metrics + verdict.

    In this format a threshold value of true means the threshold FAILED."""
    m = summary.get("metrics") or {}
    dur = m.get("http_req_duration") or {}
    reqs = m.get("http_reqs") or {}
    failed = m.get("http_req_failed") or {}
    thresholds = []
    for metric, data in m.items():
        for expr, crossed in ((data or {}).get("thresholds") or {}).items():
            thresholds.append({"metric": metric, "threshold": expr, "passed": not bool(crossed)})
    if not thresholds:
        verdict = "inconclusive"
    else:
        verdict = "fail" if any(not t["passed"] for t in thresholds) else "pass"

    def ms(key: str) -> float | None:
        v = dur.get(key)
        return round(float(v), 2) if isinstance(v, (int, float)) else None

    return {
        "requests": int(reqs.get("count") or 0),
        "rps": round(float(reqs.get("rate") or 0), 2),
        "error_rate": round(float(failed.get("value") or 0), 4),
        "avg_ms": ms("avg"), "p90_ms": ms("p(90)"), "p95_ms": ms("p(95)"),
        "p99_ms": ms("p(99)"), "max_ms": ms("max"),
        "thresholds": thresholds,
        "verdict": verdict,
    }


# ------------------------------------------------------------------ job set-up

def job_config_xml(*, repo_url: str, branch: str, script_path: str,
                   git_credentials_id: str = "", description: str = "") -> str:
    """config.xml for a Pipeline job that runs <script_path> from Git, with the
    TEST and PERF_ENV parameters declared up front (so no manual first build)."""
    creds = (f"<credentialsId>{escape(git_credentials_id)}</credentialsId>"
             if git_credentials_id else "")
    return f"""<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>{escape(description)}</description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <hudson.model.ParametersDefinitionProperty>
      <parameterDefinitions>
        <hudson.model.StringParameterDefinition>
          <name>TEST</name>
          <description>Test folder under the framework's tests/, or 'all'</description>
          <defaultValue>all</defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
        <hudson.model.StringParameterDefinition>
          <name>PERF_ENV</name>
          <description>Environment file under the framework's environments/</description>
          <defaultValue>dev</defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
      </parameterDefinitions>
    </hudson.model.ParametersDefinitionProperty>
  </properties>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps">
    <scm class="hudson.plugins.git.GitSCM" plugin="git">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>{escape(repo_url)}</url>
          {creds}
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches>
        <hudson.plugins.git.BranchSpec><name>*/{escape(branch)}</name></hudson.plugins.git.BranchSpec>
      </branches>
      <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
      <submoduleCfg class="empty-list"/>
      <extensions/>
    </scm>
    <scriptPath>{escape(script_path)}</scriptPath>
    <lightweight>true</lightweight>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>
"""


def setup_job(client: JenkinsClient, *, repo_url: str, branch: str, framework: str,
              git_credentials_id: str = "") -> str:
    """Create the job, or update it if it exists. Returns 'created' or 'updated'."""
    if not re.match(r"^(https://|ssh://|git@)[^\s<>]+$", repo_url or ""):
        raise JenkinsError("enter the Git repository URL (https://… or git@…) the job should build")
    if not re.match(r"^[A-Za-z0-9._/-]{1,100}$", branch or ""):
        raise JenkinsError("invalid branch name")
    if not re.match(r"^[a-z0-9][a-z0-9_-]{0,59}$", framework or ""):
        raise JenkinsError("invalid framework name")
    if git_credentials_id and not re.match(r"^[A-Za-z0-9._-]{1,100}$", git_credentials_id):
        raise JenkinsError("invalid Git credentials ID")
    xml = job_config_xml(
        repo_url=repo_url, branch=branch, script_path=f"{framework}/ci/Jenkinsfile",
        git_credentials_id=git_credentials_id,
        description=f"PerfAgent performance tests for '{framework}'. Managed by PerfAgent.",
    ).encode()

    segs = job_segments(client.t.job)
    exists = client.request("GET", _job_path(client.t.job) + "/api/json?tree=name")
    if exists.status == 200:
        r = client.request("POST", _job_path(client.t.job) + "/config.xml", xml, "application/xml")
        if r.status not in (200, 201):
            raise JenkinsError(f"Jenkins refused to update the job (HTTP {r.status})")
        return "updated"
    if exists.status != 404:
        raise JenkinsError(f"could not check the job in Jenkins (HTTP {exists.status})")
    parent = "".join(f"/job/{urllib.parse.quote(p, safe='')}" for p in segs[:-1])
    r = client.request("POST", f"{parent}/createItem?name={urllib.parse.quote(segs[-1])}",
                       xml, "application/xml")
    if r.status == 404 and parent:
        raise JenkinsError("the Jenkins folder doesn't exist — create the folder first")
    if r.status not in (200, 201):
        raise JenkinsError(f"Jenkins refused to create the job (HTTP {r.status}); "
                           "your user may need the 'Job/Create' permission")
    return "created"