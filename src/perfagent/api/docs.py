"""API documentation — every endpoint described in one place.

The interactive docs (/docs) and the OpenAPI file (/openapi.json) are built from this
module. Each endpoint gets:

  - a GROUP (tag), so the docs read as a handful of areas instead of one long list;
  - a one-line summary and a plain-English description;
  - an ACCESS LEVEL — what kind of thing the call does. There is no login or
    permission check in the agent today (that belongs to the hub that hosts it), but
    the levels are published in the OpenAPI file as `x-access`, so a gateway or a
    future role system can decide who may call what without re-reading the code;
  - whether it USES AI (spends tokens), published as `x-uses-ai`.

Routes pick their entry up with ``**doc("GET", "/api/...")`` in the route decorator.
tests/test_api_docs.py fails if an endpoint has no entry here, or an entry has no
endpoint — so the docs cannot drift from the code.
"""

from __future__ import annotations

from dataclasses import dataclass

API_TITLE = "AI Performance Testing Agent"

API_DESCRIPTION = """\
Plan, generate, run and report performance tests. **The AI drafts and explains; code
decides and measures; a person approves** before any load is sent.

**The flow**

1. *Conversation* or *Planning* — describe the test; the AI drafts a plan.
2. *Request data* — choose where each request value comes from (fixed, data file, generated).
3. *Scripts* — the approved plan becomes a script (deterministic: same plan, same script).
4. *Runs* — the script is run with k6 and measured live.
5. *Reports & history* — verdict, diagnosis and comparison with earlier runs.

**Access levels** (published per endpoint as `x-access`; not enforced by the agent itself)

| Level | Meaning |
|---|---|
| `read` | Only reads what is already stored. |
| `write` | Creates or changes stored data (plans, scripts, files, conversations). |
| `run` | Sends real requests or load to the system under test. |
| `integrate` | Talks to an outside system (Git, Jenkins) with credentials supplied in the call. |

Endpoints marked **Uses AI** spend tokens with the configured provider; what is sent is
redacted first (secrets, personal data, hosts).
"""

# Group name -> description. The order here is the order in the docs.
TAGS: list[dict] = [
    {"name": "Conversation",
     "description": "The multi-turn planning chat. Builds a draft plan with the user; "
                    "never generates a script or sends load."},
    {"name": "Planning",
     "description": "Draft a plan from a form, import endpoints from a spec, reopen saved "
                    "plans, and shape the load and the response checks."},
    {"name": "Request data",
     "description": "Where each value in a request comes from: a fixed value, a column of "
                    "an uploaded data file, or a value generated fresh per request — and a "
                    "preview of the requests that will be sent."},
    {"name": "Scripts",
     "description": "Turn an approved plan into a script, bring your own script, and check "
                    "a script before running it."},
    {"name": "Runs",
     "description": "Start, watch and stop a live k6 run."},
    {"name": "Reports & history",
     "description": "The verdict and report of a run, saved reports, and trends across runs."},
    {"name": "SLA profiles",
     "description": "Reusable sets of pass/fail thresholds."},
    {"name": "Git",
     "description": "Save a test to a Git repository as a ready-to-run framework, and "
                    "import tests back. Tokens are used for the one call and never stored."},
    {"name": "Jenkins",
     "description": "Run a saved test in Jenkins and follow the build. Credentials are "
                    "sent with each call and never stored."},
    {"name": "Integrations",
     "description": "The non-secret Git and Jenkins details remembered per plan."},
    {"name": "Observability",
     "description": "Audit log, AI token usage and AI call traces."},
    {"name": "System",
     "description": "Health of the app and its database, and what it can do."},
]

ACCESS_LEVELS = {
    "read": "only reads stored data",
    "write": "creates or changes stored data",
    "run": "sends real requests or load to the system under test",
    "integrate": "talks to an outside system (Git / Jenkins) with credentials from the call",
}


@dataclass(frozen=True)
class EndpointDoc:
    tag: str
    summary: str
    description: str
    access: str = "read"
    uses_ai: bool = False
    returns: str = "Successful response"


def _e(tag, summary, description, access="read", uses_ai=False, returns="Successful response"):
    return EndpointDoc(tag, summary, " ".join(description.split()), access, uses_ai, returns)


ENDPOINTS: dict[tuple[str, str], EndpointDoc] = {
    # ------------------------------------------------------------ Conversation
    ("GET", "/api/chat/config"): _e(
        "Conversation", "Is conversation mode on, and its limits",
        "Tells the UI whether the Conversation tab should be shown, and the limits in "
        "force (messages per conversation, message size).",
        returns="`enabled`, `max_turns`, `max_message_chars`."),
    ("POST", "/api/chat/sessions"): _e(
        "Conversation", "Start a conversation",
        "Opens a new planning conversation with the user's first message (and, "
        "optionally, a pasted Postman / OpenAPI / HAR collection) and runs the first "
        "turn. Secrets in the message are masked before it is stored or sent to the AI.",
        "write", True,
        "The conversation view: messages, the draft so far, what is still missing."),
    ("GET", "/api/chat/sessions"): _e(
        "Conversation", "List recent conversations",
        "The most recent planning conversations, newest first, for the "
        "'Recent conversations' menu.",
        returns="`sessions`: id, title, status, turns, linked plan."),
    ("GET", "/api/chat/sessions/{session_id}"): _e(
        "Conversation", "Open one conversation",
        "Returns a conversation as the UI shows it. Used to resume after a page "
        "refresh or an app restart.",
        returns="The conversation view."),
    ("POST", "/api/chat/sessions/{session_id}/messages"): _e(
        "Conversation", "Send the next message",
        "Adds a user message to a conversation and runs the turn: the AI updates the "
        "draft and replies. If the draft is complete and the message asks to go ahead, "
        "the plan is built in the same call.",
        "write", True, "The updated conversation view."),
    ("POST", "/api/chat/sessions/{session_id}/build"): _e(
        "Conversation", "Build the plan from the draft",
        "Hands the conversation's draft to the planner and saves the plan for review. "
        "Refused with 409 while the target or the endpoints are still missing. Nothing "
        "is generated or run.",
        "write", True, "The conversation view, including `plan` (ready for review)."),
    ("DELETE", "/api/chat/sessions/{session_id}"): _e(
        "Conversation", "Delete a conversation",
        "Forgets a conversation and its saved state. Plans already built from it are kept.",
        "write", returns="`deleted`: the conversation id."),

    # ---------------------------------------------------------------- Planning
    ("POST", "/api/plan"): _e(
        "Planning", "Draft a plan from the form",
        "The AI drafts a plan (journeys, weights, think times, thresholds) from the "
        "target, goal, load size and endpoints given. Code then forces the target, the "
        "load shape and sane thresholds. The plan is saved and returned for review.",
        "write", True,
        "`plan_id`, `load_model`, `evaluation` (grounding checks), `guardrail` (what was "
        "redacted), `rationale`, `usage`."),
    ("POST", "/api/import-endpoints"): _e(
        "Planning", "Import endpoints from a spec",
        "Reads an uploaded OpenAPI/Swagger file, Postman collection or HAR capture and "
        "returns the endpoints found, so they need not be typed. Nothing is stored and "
        "no AI is involved.",
        returns="`endpoints` (method, path, example body), `source`, `base_url`, `warnings`."),
    ("GET", "/api/plans"): _e(
        "Planning", "List saved plans",
        "Every saved plan, newest first, with its target, goal and how many scripts it has.",
        returns="`plans`."),
    ("GET", "/api/plans/{plan_id}"): _e(
        "Planning", "Open a saved plan",
        "One saved plan with its full contents and the scripts generated from it.",
        returns="`plan_id`, `target`, `goal`, `load_model`, `scripts`."),
    ("POST", "/api/load-profile"): _e(
        "Planning", "Build the load shape",
        "Turns a test type (ramp, spike, soak, stress), a peak number of users and a "
        "duration into the list of load stages. Pure calculation — the same inputs "
        "always give the same shape, and no AI is involved. Used when the size of a "
        "plan is changed during review.",
        returns="`load_profile` (stages), `max_users`, `peak_users`, `total_seconds`."),
    ("POST", "/api/suggest-checks"): _e(
        "Planning", "Suggest response checks",
        "The AI proposes checks (status, body contains, JSON field values) from a "
        "sample response pasted by the user. The sample is redacted before the AI sees "
        "it. Nothing is added to the plan until the user accepts.",
        uses_ai=True, returns="`checks`, `notes`, `guardrail` (what was redacted), `usage`."),

    # ------------------------------------------------------------ Request data
    ("POST", "/api/data"): _e(
        "Request data", "Upload a test-data file",
        "Uploads a CSV, TSV, TXT, JSON or JSONL file of real values (e.g. user names, "
        "branch codes), checks it and stores it. Only the column NAMES are ever shown "
        "to the AI; the values stay in the database for the run.",
        "write", returns="`data_file_id`, `filename`, `fields`, `row_count`, "
                         "`source_format`, `warnings`, `sample_rows`."),
    ("GET", "/api/data/{data_file_id}"): _e(
        "Request data", "Describe an uploaded data file",
        "The columns, row count and first rows of a stored data file, so the UI can "
        "show what is available to map into requests.",
        returns="`data_file_id`, `filename`, `fields`, `row_count`, `source_format`, "
                "`sample_rows`."),
    ("POST", "/api/dynamize"): _e(
        "Request data", "Suggest a source for each body field",
        "The AI looks at a request body and proposes, field by field, which values "
        "should come from the data file, which should be generated fresh per request "
        "and which should stay fixed. Returns the body with ${...} placeholders for the "
        "user to review; it does not change the plan.",
        uses_ai=True, returns="`body`, `changed_fields`, `notes`, `guardrail`, `usage`."),
    ("POST", "/api/request-preview"): _e(
        "Request data", "Preview the requests that will be sent",
        "Fills each step of a plan with real rows of the data file and sample "
        "generated values, and returns the first few requests exactly as they would be "
        "sent. Also lists any ${name} that has no source. Nothing is sent to the "
        "target and no AI is involved.",
        returns="`steps` — for each: `requests` (method, url, body), `fields` (source "
                "of each value), `run_time_values`, `undefined` — plus `row_mode`, "
                "`rows_available`."),

    # ----------------------------------------------------------------- Scripts
    ("POST", "/api/plan/{plan_id}/generate"): _e(
        "Scripts", "Approve a plan and generate its script",
        "Renders the (possibly edited) plan to a script for k6, Locust, JMeter or "
        "Gatling, attaching the data file and custom headers. Generation is "
        "deterministic — no AI. This is the human approval step: the edited plan is "
        "saved as the approved one.",
        "write", returns="`script_id`, `plan_id`, `tool`, `filename`, `content`."),
    ("POST", "/api/scripts/upload"): _e(
        "Scripts", "Use your own script",
        "Stores a hand-written or existing k6 script so it can be validated and run, "
        "skipping planning. Also used when the generated script is edited.",
        "write", returns="`script_id`, `plan_id`, `tool`, `filename`, `content`."),
    ("GET", "/api/scripts/{script_id}/download"): _e(
        "Scripts", "Download a script",
        "The script as a file.", returns="The script text, as an attachment."),
    ("POST", "/api/scripts/{script_id}/validate"): _e(
        "Scripts", "Check a script without running it",
        "Asks k6 to load the script and its options (`k6 inspect`). Catches syntax "
        "errors and bad options. No request is sent to the target.",
        returns="`ok`, `status`, `message`, `detail`."),
    ("POST", "/api/preflight"): _e(
        "Scripts", "Send one request per endpoint",
        "Before a full run, sends exactly ONE request to each endpoint of the plan — "
        "with the custom headers, a real data row and sample generated values — and "
        "reports the status of each. Answers 'will we get valid responses?'. This is "
        "not load, but it does touch the target.",
        "run", returns="`total`, `ok`, `failed`, `all_ok`, and the status per endpoint."),

    # -------------------------------------------------------------------- Runs
    ("GET", "/api/run/available"): _e(
        "Runs", "Is the load engine ready",
        "Whether k6 is present or can be fetched automatically on the first run.",
        returns="`k6` (true / false)."),
    ("POST", "/api/scripts/{script_id}/run"): _e(
        "Runs", "Start a run",
        "Starts the script with k6 and returns at once. The run continues in the "
        "background; poll the run for live metrics. This sends real load to the target.",
        "run", returns="`run_id`, `status`, `message`."),
    ("GET", "/api/runs/{run_id}"): _e(
        "Runs", "Live status of a run",
        "The run's status and the metrics measured so far (requests, error rate, "
        "throughput, percentiles), all computed in code from k6's raw output, plus the "
        "recent log lines.",
        returns="`run_id`, `status`, `message`, `elapsed_s`, `snapshot`, `logs`."),
    ("POST", "/api/runs/{run_id}/stop"): _e(
        "Runs", "Stop a run",
        "Stops a run in progress. The metrics measured up to that point are kept.",
        "run", returns="`run_id`, `status`."),
    ("GET", "/api/runs/{run_id}/logs/download"): _e(
        "Runs", "Download a run's logs",
        "k6's output for the run — threshold crossings, the checks summary and the "
        "script's own console messages — as a text file. Works for a live run and for "
        "a saved one.",
        returns="The log text, as an attachment."),

    # ------------------------------------------------------- Reports & history
    ("GET", "/api/runs/{run_id}/report"): _e(
        "Reports & history", "Report of a finished run",
        "The pass/fail verdict (decided in code against the plan's thresholds), the "
        "diagnosis, the comparison with the previous run of the same plan, and a short "
        "summary written by the AI from those numbers (checked so it cannot cite a "
        "figure that was not measured). The report is saved.",
        "write", True,
        "`run_id`, `target`, `verdict`, `narrative`, `evaluation`, `diagnostics`, "
        "`baseline`, `logs`."),
    ("GET", "/api/runs/{run_id}/report/download"): _e(
        "Reports & history", "Download the report",
        "The full report as a self-contained HTML file.",
        uses_ai=True, returns="An HTML file, as an attachment."),
    ("GET", "/api/runs"): _e(
        "Reports & history", "List past runs",
        "Runs that have a saved report, newest first.",
        returns="`runs`."),
    ("GET", "/api/runs/trend"): _e(
        "Reports & history", "Trend across runs of a plan",
        "The key metrics of a plan's recent runs, oldest to newest, for the trend chart.",
        returns="`points`."),
    ("GET", "/api/runs/{result_id}/saved-report"): _e(
        "Reports & history", "Reopen a saved report",
        "A previously saved report, exactly as it was produced.",
        returns="The saved report."),

    # ------------------------------------------------------------ SLA profiles
    ("GET", "/api/sla"): _e(
        "SLA profiles", "List SLA profiles",
        "The saved sets of pass/fail thresholds.", returns="`profiles`."),
    ("POST", "/api/sla"): _e(
        "SLA profiles", "Save an SLA profile",
        "Saves a named set of thresholds so it can be applied to other plans.",
        "write", returns="`id`, `name`."),
    ("DELETE", "/api/sla/{sla_id}"): _e(
        "SLA profiles", "Delete an SLA profile",
        "Removes a saved SLA profile. Plans that already use its thresholds are not changed.",
        "write", returns="`deleted`."),

    # --------------------------------------------------------------------- Git
    ("GET", "/api/export/settings"): _e(
        "Git", "Git export options",
        "The Git hosts users may push to (if restricted) and the CI systems a pipeline "
        "file can be generated for.",
        returns="`allowed_hosts`, `ci_options`."),
    ("POST", "/api/scripts/{script_id}/export/git"): _e(
        "Git", "Save a test to Git",
        "Builds a ready-to-run performance framework around the approved k6 test (test, "
        "config, CI pipeline file, README) and commits and pushes it to the repository "
        "and branch given. The access token is used for this call only and never stored.",
        "integrate", returns="`framework`, `test`, `repo_url`, `branch`, `commit`, "
                             "`changed`, `files`, `required_secrets`, `warnings`."),
    ("POST", "/api/scripts/{script_id}/export/zip"): _e(
        "Git", "Download a test as a framework zip",
        "The same framework as 'Save a test to Git', as a .zip download instead of a push.",
        returns="A .zip file, as an attachment."),
    ("POST", "/api/git/scan"): _e(
        "Git", "Browse a repository for tests",
        "Lists the PerfAgent tests and other load scripts found in a repository branch. "
        "Read-only; the token is used for this call only.",
        "integrate", returns="`repo_url`, `branch`, `commit`, `frameworks` (importable "
                             "tests), `other_scripts` (viewable), `truncated`."),
    ("POST", "/api/git/import"): _e(
        "Git", "Import a test from Git",
        "Loads one PerfAgent test from a repository back as an editable plan (and its "
        "data file, if it was committed).",
        "integrate", returns="`plan_id`, `load_model`, `framework`, `test`, `commit`, "
                             "`data_file_id`, `data_fields`, `missing_secrets`, `warnings`."),
    ("POST", "/api/git/script"): _e(
        "Git", "View another script from Git",
        "Returns the text of a script in the repository that was not made by PerfAgent, "
        "for reference or to run as your own script.",
        "integrate", returns="The script's path, tool and content."),

    # ----------------------------------------------------------------- Jenkins
    ("GET", "/api/jenkins/settings"): _e(
        "Jenkins", "Jenkins options",
        "The Jenkins hosts users may call, if restricted.", returns="`allowed_hosts`."),
    ("POST", "/api/jenkins/trigger"): _e(
        "Jenkins", "Start a Jenkins build",
        "Starts the Jenkins job for a saved test with the test name and environment as "
        "parameters. This causes Jenkins to run the load test.",
        "integrate", returns="`queue_id` (to follow), `job`, `warnings`."),
    ("POST", "/api/jenkins/status"): _e(
        "Jenkins", "Follow a Jenkins build",
        "Whether the build is queued, running or finished, the next part of its console "
        "output, and the k6 results once it is done.",
        "integrate", returns="`state`, `build_number`, `build_url`, `log` (+ `log_next`, "
                             "`log_more`), `result`, `results`, `verdict`."),
    ("POST", "/api/jenkins/stop"): _e(
        "Jenkins", "Stop a Jenkins build",
        "Aborts a running build.", "integrate", returns="`stopped`."),
    ("POST", "/api/jenkins/setup-job"): _e(
        "Jenkins", "Create or update the Jenkins job",
        "Creates the Pipeline job for a framework in Jenkins, or updates it, so the "
        "saved tests can be run there.",
        "integrate", returns="`action` (created / updated), `job`, `warnings`."),

    # ------------------------------------------------------------ Integrations
    ("GET", "/api/integrations"): _e(
        "Integrations", "Saved Git and Jenkins details",
        "The non-secret details remembered for a plan (repository, branch, job) and the "
        "last-used defaults, so forms can be pre-filled. Tokens are never stored, so "
        "they are never returned.",
        returns="`plan_id`, `git`, `jenkins`, `saved`."),
    ("DELETE", "/api/integrations"): _e(
        "Integrations", "Forget saved details",
        "Forgets the saved Git details, Jenkins details, or both, for a plan.",
        "write", returns="What remains saved: `plan_id`, `git`, `jenkins`, `saved`."),

    # ----------------------------------------------------------- Observability
    ("GET", "/api/audit"): _e(
        "Observability", "Audit log",
        "Recent actions — plans created, scripts generated, runs started, pushes to "
        "Git — with when, on what, and the tokens spent.",
        returns="`events`."),
    ("GET", "/api/usage/total"): _e(
        "Observability", "AI usage so far",
        "Total tokens and a rough cost across all AI calls.",
        returns="`tokens`, `cost_usd`, `ai_calls`."),
    ("GET", "/api/traces"): _e(
        "Observability", "AI call traces",
        "One record per AI call: which step made it, the model, tokens, time taken, "
        "whether it succeeded and how many values were redacted. For debugging and "
        "cost review; prompts are stored redacted.",
        returns="`traces`."),

    # ------------------------------------------------------------------ System
    ("GET", "/api/health"): _e(
        "System", "Health check",
        "Whether the app is up and can reach its database, which database is in use "
        "(SQLite or Postgres) and whether its tables are up to date. Returns 503 if the "
        "database cannot be reached. Suitable as a container health check.",
        returns="`status`, `database` (backend, host, name, schema state)."),
    ("GET", "/api/tools"): _e(
        "System", "Supported load tools",
        "The load tools a script can be generated for.", returns="`tools`."),
}


def doc(method: str, path: str) -> dict:
    """Decorator arguments for a route: ``@app.get(path, **doc("GET", path))``."""
    entry = ENDPOINTS[(method.upper(), path)]
    parts = [entry.description,
             f"**Access level:** `{entry.access}` — {ACCESS_LEVELS[entry.access]}."]
    if entry.uses_ai:
        parts.append("**Uses AI:** yes — spends tokens; inputs are redacted first.")
    return {
        "tags": [entry.tag],
        "summary": entry.summary,
        "description": "\n\n".join(parts),
        "response_description": entry.returns,
        "openapi_extra": {"x-access": entry.access, "x-uses-ai": entry.uses_ai},
    }


__all__ = ["API_TITLE", "API_DESCRIPTION", "TAGS", "ACCESS_LEVELS", "ENDPOINTS",
           "EndpointDoc", "doc"]
