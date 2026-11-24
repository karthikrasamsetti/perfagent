<div align="center">

# PerfAgent

**Plan, verify, run, and explain HTTP performance tests from one workspace.**

Start with a URL, API endpoints, a conversation, or an import. Review the proposed workload,
verify the requests and response checks with minimal traffic, then start a k6 load test.
Use the dashboard to compare saved runs and the report to explain the result.
</div>

> [!IMPORTANT]
> Run PerfAgent against targets you are authorized to test. Review sends no target traffic.
> Verify sends test requests. Starting a full load run is a separate action.

---

## Table of contents

Start with the [project workflow](PROJECT_WORKFLOW.md) for project creation, separate script/Git imports, workload profiles, project dashboards and the admin overview. The [React frontend guide](frontend/README.md) covers development and production builds; [SPA_MIGRATION.md](SPA_MIGRATION.md) records the remaining incremental refactors.

- [Screenshots](#screenshots)
- [Technology stack](#technology-stack)
- [AI roles](#ai-roles)
- [Why this exists](#why-this-exists)
- [Four ways to start](#four-ways-to-start)
- [Reviewing the plan](#reviewing-the-plan)
- [Conversation mode](#conversation-mode)
- [The 5-step workflow](#the-5-step-workflow)
- [Feature highlights](#feature-highlights)
- [Dynamic test data — the three sources](#dynamic-test-data--the-three-sources)
- [Validating the response — assertions & suggested checks](#validating-the-response--assertions--suggested-checks)
- [Quick start](#quick-start)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the app](#running-the-app)
- [First UI test](#first-ui-test)
- [Save tests to Git and import them back](#save-tests-to-git-and-import-them-back)
- [Run in Jenkins](#run-in-jenkins-step-3)
- [Database — SQLite or Postgres](#database--sqlite-or-postgres)
- [API reference](#api-reference)
- [Running the tests](#running-the-tests)
- [How it works](#how-it-works)
- [Data guardrails](#data-guardrails)
- [AI evaluation](#ai-evaluation)
- [Observability — logging, audit & tokens](#observability--logging-audit--tokens)
- [Architecture](#architecture)
- [Project layout](#project-layout)
- [Safety notes](#safety-notes)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

---

## Screenshots

The screenshots use sample projects, requests, and run results.

| Performance dashboard | Run report |
|---|---|
| [![Historical metrics, failures, and regressions](docs/screenshots/dashboard.png)](docs/screenshots/dashboard.png) | [![Run verdict, explanation, and key evidence](docs/screenshots/report.png)](docs/screenshots/report.png) |

<details>
<summary>Project and test workflow screenshots</summary>

| Page | Screenshot |
|---|---|
| Projects | [Project workspace](docs/screenshots/projects.png) |
| Describe | [Target, endpoints, load, and response checks](docs/screenshots/describe.png) |
| Review Plan | [Plan summary, editable requests, and test data](docs/screenshots/review-plan.png) |
| Verify | [Verification and execution controls](docs/screenshots/verify.png) |
| Script history | [Latest and previous script versions](docs/screenshots/script-history.png) |
| Run | [Live metrics and endpoint measurements](docs/screenshots/run.png) |
| Project workspace | [Searchable project tests, Git framework preview, and reports](docs/screenshots/test-library.png) |
| Monitoring | [Monitoring view](docs/screenshots/monitoring.png) |
| Activity | [Activity and AI usage](docs/screenshots/activity.png) |
| Administration | [Admin overview](docs/screenshots/administration.png) |

</details>

## Technology stack

| Layer | Technologies and responsibilities |
|---|---|
| Frontend | React 19, TypeScript, React Router 7, Vite 8, CSS, and Canvas charts. FastAPI serves the production build. |
| API and contracts | Python 3.11+, FastAPI, Uvicorn, Pydantic, and OpenAPI. Shared contracts describe targets, workloads, requests, assertions, and thresholds. |
| Persistence | SQLAlchemy 2, Alembic, SQLite for local use, and PostgreSQL through psycopg. LangGraph uses a SQLite or PostgreSQL checkpoint backend for conversation state. |
| Planning and reporting | OpenAI or Anthropic through the server-side provider adapter, Instructor for structured responses, and LangGraph for conversation state and routing. |
| Execution | k6 for the integrated verification and live-run workflow. Python and Jinja2 render scripts. The project also has generators for Locust, JMeter, and Gatling. |
| Observability and QA | structlog, Prometheus metrics, pytest, Vitest, and a headless Chromium smoke harness with fixture APIs. |

## AI roles

| Role | What it helps with | Implementation |
|---|---|---|
| Conversation assistant | Collects missing details and prepares a draft from a conversation. | [LangGraph conversation workflow](src/perfagent/chat/graph.py) |
| Test planner | Suggests journeys, traffic weights, and checks. Application code restores explicit inputs and applies the selected workload rules. | [Planner](src/perfagent/planner/planner.py) |
| Request data and check suggestions | Suggests value sources for a body or response assertions from a supplied sample, for the user to review. | [Dynamic data suggestions](src/perfagent/dynamize.py), [check suggestions](src/perfagent/check_suggest.py) |
| Report narrator | Explains computed results and can fall back to a rule-based summary when a provider is unavailable. | [Report narrator](src/perfagent/analyzer/narrator.py) |

These roles share the application's guarded provider interface. Application code controls validation, script generation, run execution, metrics, and the verdict. The user selects when to verify or run.

## Why this exists

Performance testing is slow and expert-bound: deciding *what* to test is tribal knowledge,
writing load scripts (with auth tokens and realistic data) is error-prone, and reading
results is inconsistent. This agent compresses that loop — **minutes instead of hours** —
while keeping humans in control of every decision that matters and keeping the AI away from
anything that must be exact.

| Traditional performance testing | With this agent |
|---|---|
| Hand-pick endpoints & journeys | AI drafts realistic journeys from your endpoints (or an imported spec) |
| Hand-write & maintain scripts | Deterministic generation — the same plan always yields the same script |
| Set up auth/token flow manually | AI auto-detects login → token → reuse (correlation) |
| Hand-wire unique/random request data | AI assigns dynamic generators + your CSV data per field |
| Stare at raw metrics | A report dashboard + automatic bottleneck diagnosis |
| "Is it worse than last time?" — unknown | Automatic **baseline comparison** flags regressions |
| Reports lost after the run | Every run's report is **saved** and reopenable |
| Status-code-only checks | **Assertions** validate the response body, not just 2xx |
| No visibility into why a check failed | A **response-checks panel** + live/saved **run logs** show exactly what failed |
| One load tool | Generate for **k6, Locust, JMeter, Gatling** from one plan |
| Scripts stuck in the tool | **Save to Git** as a CI-ready framework; **run in Jenkins** and follow it live |

---

## Four ways to start

Step 1 is one row of tabs — pick how you want to begin:

| Tab | What it does |
|---|---|
| **💬 Conversation** | A real back-and-forth. Say what you want, answer what the agent still needs, keep refining ("make it 200 users", "drop /checkout"), and build the plan when the draft looks right. See [Conversation mode](#conversation-mode). |
| **📝 Manual form** | Type or import the target and endpoints yourself; the AI drafts the plan from them. |
| **⚡ My k6 script** | Already have a script? Upload or paste it and go straight to validating and running it — no AI planning. |
| **📂 Import from Git** | Pull a test PerfAgent saved to Git back as an editable plan, or pick up another k6 script from the repository. |

Conversation and Manual both end in the same place: a plan you review and approve.
Inline **ℹ️ tooltips** explain every concept, so a QA engineer can use it without a walkthrough.

---

## Reviewing the plan

Start with **Before you approve** and **What will run**. Confirm the target, masked authentication,
planned load shape, journey order, and pass rules. Open a request with its **Edit** button to
change its method, path, body, or response checks.

- **Response checks** verify the content that came back. For example, enter `order.id` under the
  Describe endpoint's optional response check, then confirm the field-existence rule in Review.
  For a value comparison, edit the request's response checks in Review.
- **Changing values** can come from uploaded data, runtime generators, or an earlier response
  in the same journey. Review flags unresolved values and links to the affected request.
- **Preview sample requests** shows sample URLs and bodies. **Approve & continue to Verify**
  generates the execution script. Use **Verify** to send requests and evaluate the checks.

---

## Conversation mode

A multi-turn chat that builds the plan with you. A **Draft so far** panel beside the chat
shows the target, endpoints and load size as they firm up, so the plan is never a surprise.

- **The draft is the source of truth, not the chat text.** Each turn the AI returns a
  schema-validated update; code merges it into the draft, so a later message can't silently
  drop something you said earlier.
- **Code decides when it's ready.** A plan can be built once there is a target URL and at
  least one endpoint. Users and duration fall back to 20 users / 60 s and are marked
  *default* until you state them.
- **Build when you're happy** — press **Build plan**, or just say "go ahead". The plan opens
  in Step 2 like any other. Come back and keep chatting to refine it; the button becomes
  **Rebuild plan** when the draft has changed.
- **It only plans.** The conversation never generates a script or fires load — you still
  review and approve in Step 2.
- **Conversations are saved.** A refresh or an app restart resumes where you left off, and
  recent conversations can be reopened from the drop-down.
- **Secrets are masked before they are stored or sent.** Passwords, tokens and emails typed
  into the chat are replaced with placeholders before the message is saved and before the AI
  sees it; set real values in the review step or use a data file.

Under the hood it is a small **LangGraph** graph — `understand → await_user → build_plan` —
checkpointed per conversation in `perfagent_chat.db`. The wait for your reply is a LangGraph
*interrupt*, the same mechanism the approval gate will use when the run steps join the graph.

| Setting (`.env`) | Default | Meaning |
|---|---|---|
| `CHAT_CONVERSATION_ENABLED` | `true` | Turn the mode off to hide the Conversation tab. |
| `CHAT_CHECKPOINT_DB` | `perfagent_chat.db` | Where conversations are saved; `:memory:` keeps them in memory only. |
| `CHAT_MAX_TURNS` | `40` | Most user messages in one conversation. |
| `CHAT_HISTORY_WINDOW` | `12` | Recent messages replayed to the AI each turn (the draft carries the rest). |
| `CHAT_MAX_MESSAGE_CHARS` | `8000` | Largest single message. |

API: `POST /api/chat/sessions`, `POST /api/chat/sessions/{id}/messages`,
`POST /api/chat/sessions/{id}/build`, `GET /api/chat/sessions[/{id}]`,
`DELETE /api/chat/sessions/{id}`.

---

## The 5-step workflow

1. **Describe** the target, endpoints, response checks, and workload. Choose VU-based traffic or a request-rate goal for a single HTTP request per iteration.
2. **Review Plan** to inspect the draft, change any request, attach test data, and confirm checks and thresholds.
3. **Verify** the generated or imported script. Validate its syntax, verify the requests and assertions, and optionally run a short smoke test.
4. **Run** the load test and watch throughput, latency, errors, VUs, dropped iterations, and live logs.
5. **Report** on the verdict and the evidence behind it. Reopen saved reports, compare compatible runs, or export a standalone HTML report.

---

## Feature highlights

### 🧭 Discover & import
- **OpenAPI / Swagger** (JSON **or YAML**), **Postman collections** (incl. nested folders),
  **HAR captures** — endpoints, sample bodies, and target URL imported automatically.
- **Import from Git** — pull a test PerfAgent previously saved back as an editable plan, or
  pick up another k6 script from a repository.

### 🔐 Real-world auth & data
- **Correlation** — capture a value from a response (**JSON field, header, cookie, or
  regex**, incl. array indices like `data[0].id`) and reuse it later as `${var}`. Auto-set-up for login flows.
- **Assertions** — validate the response, not just the status: body **contains** / **does NOT
  contain** text, **status code is** N, a **JSON field compares** (eq/ne/gt/lt/contains), or
  **response time under** N ms. A failed assertion counts as an error and fails the run.
- **✨ Suggest checks from a response** — paste a real API response and the AI proposes the
  right checks (which elements must be present, which errors to guard against, which numbers
  should be positive); the response is redacted before it's sent, and you keep only the checks you want.
- **Custom headers** — global `Authorization` / API-key headers; values can use captured vars.
- **Dynamic test data** — three sources per field (see below), assigned by the AI with one click.

### ⏱ Realistic load
- **Test types** — ramp, spike, soak, stress, each a genuinely different load shape.
- **Environment & TLS** — tag a run with an environment name (dev/staging/prod), and for test
  or dev hosts optionally **skip TLS certificate verification** (never against production).
- **Protocols** — REST/HTTP and **GraphQL** (a step can send a `{query, variables}` request).
- **Multi-tool** — generate scripts for **k6** (primary, with a live runner), **Locust**,
  **JMeter** (`.jmx`), and **Gatling** (`.scala`) from the same plan.
- **Editable plan form** — scenarios, weights, think-times, thresholds (raw-JSON toggle too).

### ✅ Trust & safety
- **Data guardrails** — secrets/PII/URLs redacted before the AI; output scrubbed.
- **AI evaluation** — plan grounding (no invented endpoints) + report citation (no fabricated numbers).
- **Fail-closed verdict** — an unmeasurable threshold → **INCONCLUSIVE**, never a silent PASS.

### 🔎 Run & diagnose
- **Pre-flight check**, **script validation** (`k6 inspect`), **live monitoring + chart**,
  **live run logs** (k6's output streamed as it runs — threshold crossings, the checks
  summary, and your script's own `console.*` messages), a **diagnosis engine** (bottlenecks,
  latency tail, concurrency), and **baseline/regression**.
- **Editable script** — tweak the generated k6 before running (e.g. add custom `console.log`
  debugging, or your own validation); **Regenerate** restores the deterministic version.

### 📊 Report & history
- **Performance dashboard** shows comparable historical runs across latency, throughput, error rate, and daily outcomes, with environment and release filters and links to saved reports.
- **Run report** opens with the verdict, What happened, and linked key evidence, followed by thresholds, synchronized timelines, endpoint rankings, and baseline comparison.
- **Response checks panel** — each assertion with its pass/fail count, so you can see exactly
  which checks failed and why the run passed or failed.
- **Run logs** — the full k6 output for the run is shown on the report, **saved with it**, and
  **downloadable as a `.txt`** — reopen a run from history and its logs are still there.
- **Time-series + trend charts** — latency/RPS/errors over the run, and p95/error trends across recent runs.
- **SLA profiles** — save reusable threshold sets (e.g. "p95<300ms, errors<1%") and apply to any plan.
- **Runs & reports history** — every finished run saved; click to reopen its full report.
- **Downloadable HTML report** for stakeholders.

### 🚀 Ship to CI/CD
- **Save to Git** — export the test into a named k6 framework with ready-made **GitHub
  Actions, Jenkins, Azure DevOps and GitLab** pipelines; secrets are never committed.
- **Run in Jenkins** — trigger the pipeline for a saved test and follow it live in PerfAgent
  (queued → running → finished, console log streaming, archived k6 results and verdict).

### 🧰 Convenience
- **Run an existing script**, **saved plans** (reopen & re-run), **token-usage** visibility,
  and **saved (non-secret) Git/Jenkins details** so you don't retype them.

---

## Dynamic test data — the three sources

Real request bodies mix three kinds of values. On the Review step, open a step and its
**Request data** table lists every field of the body with a **Comes from** choice — no
`${...}` to type by hand:

| Comes from | When to use | You pick | In the script |
|---|---|---|---|
| **Fixed value** | A constant | the value (text, number, true/false, empty) | kept as-is |
| **From data file** | A *real existing* value the API validates | a column of the uploaded file | `row.branch` (k6 `SharedArray`) |
| **Generated** | A value that must be *new for every request* | Unique ID, Unique email, Random number between…, Random pick from a list…, names, addresses, dates… | self-contained k6 helpers (`uuidv4()`, `fakeName()`, …) |

A fourth kind appears on its own: **From an earlier step** — a value captured from a
previous response (for example a login token).

**How to make every request unique**

1. On the Review step, upload the file under **2 · Test data file**. Its columns and first
   rows are shown.
2. Under **3 · Journeys**, click the step. For each field choose *From data file* (a column
   with the same name is picked for you) or *Generated*. **✨ Suggest with AI** proposes a
   source for every field at once — review it, or press *Undo*.
3. Choose how the rows are used:

   | Use the rows | Behaviour |
   |---|---|
   | In random order *(default)* | Any row; a row can be used more than once. |
   | In file order | Row 1, 2, 3 … shared by all virtual users; starts again at the top. |
   | Each row once | No row is ever reused. With several journeys each gets its own share of the rows. When the rows run out the test stops and says so. |

4. Click **🔍 Preview the requests** to see three real examples per step.

Nested bodies work the same way (fields are listed as `address.city`, `items[0].sku`);
*Edit as JSON* is there for structural changes. A name that is neither a column, nor
generated, nor captured is flagged — in the step, in the preview and before generating —
because it would be sent empty.

The same `${...}` placeholders still work if you prefer to type them:
`${username}` (column), `${uuid}`, `${randomEmail}`, `${randomInt(1,5)}`,
`${randomString(8)}`, `${randomFrom(a,b,c)}`, `${timestamp}`, `${sequential}`,
`${dateOffset(3,'days')}`, `${randomFullName}`, `${randomCity}` and the other realistic
generators. Postman-style `{{var}}` / `{{$randomX}}` is also accepted and converted. The
realistic generators are **self-contained helper functions** — no external faker library.

Only the **column names** of a data file are ever sent to the AI; the values stay in the
database for the run. Data files are built into **k6** scripts (the other tools ignore them).
The pre-flight check fills in a real row and sample generated values too, so it sends
realistic requests.

---

## Validating the response — assertions & suggested checks

A load test that only checks the HTTP status can **pass while the API is returning errors** —
many APIs answer `200 OK` with an error payload in the body. Assertions close that gap.

**Assertion kinds** (added per step, in plain English):

| Check | Passes when | Example |
|---|---|---|
| **Response body contains** | the body includes the text | contains `<Rate>` |
| **Response body does NOT contain** | the body is free of the text | does NOT contain `Invalid Parameters` |
| **Status code is** | the status equals N | status is `200` |
| **JSON field compares** | a field eq/ne/gt/lt/contains a value | `data.total` **gt** `0` |
| **Response time under (ms)** | the request finished in time | under `2000` ms |

A failed assertion is counted as an **error** (not just a failed k6 check), so it raises the
error rate and can **fail the run** — assertions are enforced, not decorative. The
**response-checks panel** on the report shows each check's pass/fail count.

**✨ Suggest checks from a response** — rather than hand-writing every check, paste a **real
response** you captured (from Postman or curl) and the AI proposes a layered set: the
structural elements that should always be present, the error strings to guard against, and
the numeric fields that should be positive. You review the list and keep what you want. The
pasted response is **redacted** (secrets/PII removed) before it is sent to the AI — only the
structure is shared.

---

## Quick start

```bash
# 1. install
uv sync

# 2. configure your LLM key
cp .env.example .env          # macOS / Linux; PowerShell: Copy-Item .env.example .env

# 3. run the agent
uv run uvicorn perfagent.api.app:app --reload --port 8080

# 4. (separate terminal) start the safe demo target
uv run python -m perfagent.sample_target.app

# 5. open http://127.0.0.1:8080  →  describe (chat or form) → approve → run
```

---

## Prerequisites

| Requirement | Why | Check | Get it |
|---|---|---|---|
| **Python 3.11+** | The service is Python | `python --version` | <https://www.python.org/downloads/> |
| **uv** *(or pip)* | Dependency manager | `uv --version` | <https://docs.astral.sh/uv/getting-started/installation/> |
| **k6** *(optional)* | Runs & validates the load tests — **downloaded automatically** on first run if missing | `k6 version` | Not needed; see *k6 is installed automatically* below |
| **Git 2.31+** | Clone / push, and Save to Git / Import from Git | `git --version` | <https://git-scm.com/downloads> |
| **LLM API key** | AI planning + narration | — | [OpenAI](https://platform.openai.com/) · [Anthropic](https://console.anthropic.com/) |

> [!NOTE]
> - You **don't** need to install k6. On the first run or validation PerfAgent downloads the pinned, checksum-verified k6 into `~/.perfagent/bin/` (see below).
> - You **don't** need an API key to run the test suite — the tests mock the LLM.
> - Set a **spend cap** on your provider account before using the AI features.

---

## Setup

<details>
<summary><b>Option A — uv (recommended)</b></summary>

```bash
git clone https://github.com/karthikrasamsetti/perfagent.git
cd perfagent
uv sync
```
</details>

<details>
<summary><b>Option B — pip + venv</b></summary>

```bash
git clone https://github.com/karthikrasamsetti/perfagent.git
cd perfagent
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on mac/linux)
pip install -r requirements.txt
```
</details>

Then create your environment file (`cp .env.example .env` on macOS/Linux or `Copy-Item .env.example .env` in PowerShell) and fill it in:

```ini
LLM_PROVIDER=openai             # or "anthropic"
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=
LOG_LEVEL=INFO
GUARDRAIL_DEBUG=0               # set 1 temporarily to log the (redacted) prompt sent to the AI
```

> Keep provider keys and target credentials in local server-side configuration. Commit only placeholders in `.env.example`.

---

## Running the app

**Terminal 1 — the agent (web UI + API):**
```bash
uv run uvicorn perfagent.api.app:app --reload --port 8080
```
Open **<http://127.0.0.1:8080>**.

**Terminal 2 — the built-in mock target (safe to load-test):**
```bash
uv run python -m perfagent.sample_target.app      # http://127.0.0.1:8000
```

Then follow **Describe → Review Plan → Verify → Run → Report**. For frontend development, run `npm ci` and `npm run dev` from `frontend/` while the API is running. See the [frontend guide](frontend/README.md).

## First UI test

Start PerfAgent and the sample target using the commands above. Use port **8080** for the packaged UI or the URL printed by Vite for frontend development. The sample target runs on port **8000**.

1. Create a project and select **Open project**. Confirm the workspace shows its tests and the configured Git framework. The tree previews the export layout. **Import / sync Git** is where you browse a repository.
2. Choose **Create test**, give it a unique name, and enter `http://127.0.0.1:8000` and `POST /checkout` in Describe. Set the optional response check to `order_id`. The sample response contains that field. AI drafting uses the provider configured in `.env`.
3. Use a small workload such as **2 peak VUs for 15 seconds**. In Review, confirm the path, response check, load chart, and thresholds. **Preview sample requests** displays sample input. **Approve & continue to Verify** saves the script version.
4. Select **Verify test** and confirm the response check passes. Start the load test and compare the dashboard measurements with the saved report. Open the report and download the standalone HTML.
5. Return to the plan and approve it again without edits. Verify should show **Latest version reused — no changes**. Then change a threshold and approve again. From **Project workspace → View history**, confirm you can inspect or download the older script while Verify stays on the latest version. Smoke run artifacts have a separate group.

---

### k6 is installed automatically

PerfAgent looks for k6 in this order and uses the first one it finds:

1. `PERFAGENT_K6_PATH` — an explicit path to a k6 binary.
2. A bundled copy at `src/perfagent/runner/bin/<os>-<arch>/k6` (`k6.exe` on Windows), e.g. `windows-amd64`, `linux-amd64`, `macos-arm64`.
3. The cache at `~/.perfagent/bin/k6-v1.3.0/` (change the base folder with `PERFAGENT_HOME`).
4. A `k6` already on `PATH`.
5. Otherwise it downloads the official k6 v1.3.0 for this OS from GitHub, verifies its SHA-256
   against a hash pinned in `runner/k6_binary.py`, and stores it in the cache (step 3).

The first run shows "Setting up the load engine (first run only)…" while this happens. For machines
without internet access, use option 1 or 2. In Docker, install k6 in the image and set
`PERFAGENT_K6_PATH` so nothing is downloaded at runtime.

> [!NOTE]
> k6 prints Unicode (box-drawing and ✓/✗ characters) in its summary. PerfAgent decodes k6's
> output as UTF-8 so the **run logs** render those characters correctly on every platform,
> including Windows.

## Save tests to Git and import them back

### Save to Git (Step 3)

After generating a k6 script, the **Save to Git for CI/CD** card exports it into a named
framework and pushes it. Enter a framework name, a test name, the repository URL, branch
and an access token with push rights (not needed for SSH URLs). The token is used for that
push only and is never stored; no user name is needed. The exported script is built by the
**same deterministic generator** used in the app, so it carries your assertions, correlation,
dynamic data, GraphQL and TLS settings — with secret header values swapped for CI-provided
environment variables.

```
<framework>/
  tests/<test>/loadtest.js · plan.json · test.json
  environments/dev.env          BASE_URL (copy for uat.env, staging.env, …)
  scripts/run-tests.sh · .ps1   run one test or all
  ci/Jenkinsfile · azure-pipelines.yml · gitlab-ci.yml
  README.md · perfagent.json
.github/workflows/perf-<framework>.yml
```

* Pushing into an existing repository only **adds** files; nothing else is touched.
  PerfAgent refuses to write into a folder it didn't create, so pick a new framework name.
* Secret header values are never committed: the script reads `PERF_HEADER_<NAME>` from the
  environment and stops if one is missing. Add them as CI secrets.
* Test data is only committed if you tick the box. A final scan aborts the push if any secret
  value ended up in a file.
* Thresholds are enforced by k6, so a breach exits with code 99 and fails the pipeline.
* Exporting again with the same names updates the test in a new commit.
* **Download framework (.zip)** gives the same files without Git.
* Uploaded scripts (the "My k6 script" tab) can't be saved to Git yet.

### Import from Git (a tab on Step 1)

**Import an existing test from Git** lists what's on a branch:

* **Tests PerfAgent saved** — *Import* loads one back as an editable plan (Step 2), asking
  again for its secrets; committed test data comes along. Tests whose `loadtest.js` was
  edited by hand are flagged, because PerfAgent rebuilds scripts from the plan.
* **Other load-test scripts** (k6, Locust, JMeter) — *View* shows them; a k6 script can be
  loaded with *Use this script*, exactly like the "My k6 script" tab.

Every push and import is recorded in the activity log. The server needs `git` 2.31+.
Admins can set `GIT_ALLOWED_HOSTS`, `GIT_AUTHOR_NAME` and `GIT_AUTHOR_EMAIL` in `.env`.

API: `POST /api/scripts/{id}/export/git`, `POST /api/scripts/{id}/export/zip`,
`GET /api/export/settings`, `POST /api/git/scan`, `POST /api/git/import`, `POST /api/git/script`.

## Run in Jenkins (Step 3)

The **Run in Jenkins** card triggers the Jenkins pipeline for a test you saved to Git and
follows it in PerfAgent: queued → running → finished, with the console log streaming in, a
link to the build, and — when it finishes — the k6 results the Jenkinsfile archived
(requests, req/sec, error rate, avg / p95 / max, each threshold, and a PASS / FAIL verdict).
**Stop** aborts the build.

Enter the Jenkins URL, your Jenkins user name, an **API token** (Jenkins → your name →
Security → API Token), the job name (`folder/job` for folders), the test (or `all`) and the
environment. The token is sent with each call and never stored.

**Set up Jenkins job** creates the Pipeline job — or updates it if it exists — pointing at
`<framework>/ci/Jenkinsfile` in your repository, with the `TEST` and `PERF_ENV` parameters
declared, so no manual first build is needed (needs the *Job/Create* permission; give a Git
credentials ID for private repositories). If you create the job by hand instead, run it once
in Jenkins so it learns its parameters.

Jenkins side: Pipeline + Git plugins; a Linux/macOS agent with `curl`, `sha256sum` and `tar`, or a
Windows agent with PowerShell (the Jenkinsfile picks the right one and downloads k6 once per
workspace, verifying its checksum); and a
*Secret text* credential for each secret the test needs (e.g. `PERF_HEADER_AUTHORIZATION`).
PerfAgent must be able to reach Jenkins, and Jenkins must reach Git and the application.
Admins can restrict which Jenkins servers may be called with `JENKINS_ALLOWED_HOSTS`.

API: `POST /api/jenkins/trigger`, `/api/jenkins/status`, `/api/jenkins/stop`, `/api/jenkins/setup-job`.

### Saved Git and Jenkins details

PerfAgent remembers the **non-secret** details you used, per plan, so you don't retype them:
the Git repository, branch, framework, test and pipelines; the Jenkins URL, user name, job,
test and environment, and the job set-up details (repository, branch, framework, Git
credentials ID). They are saved only after something **succeeds** — a push, an import, a
Jenkins run or job set-up — and filled in when you open the plan again from *Saved plans*.
A brand-new plan starts with the last-used repository, branch, Jenkins URL, user name,
Git credentials ID and environment.

**Never saved:** Git tokens, Jenkins API tokens and test secrets — you enter those each time.
URLs that contain credentials are refused. *Forget saved details* on each card removes them
(for that plan and from the last-used defaults). They live in the `integration_settings`
table, which is added automatically to existing databases.

API: `GET /api/integrations?plan_id=…`, `DELETE /api/integrations?plan_id=…&section=git|jenkins|all`.

## Database — SQLite or Postgres

One setting decides where everything is stored (plans, scripts, runs, reports, audit,
traces, saved integrations and chat conversations):

| `DATABASE_URL` in `.env` | Result |
|---|---|
| *(not set)* | SQLite — a local file `perfagent.db` (plus `perfagent_chat.db` for conversations). Nothing to install. |
| `postgresql://user:password@host:5432/perfagent` | Postgres — a shared database server, for hosting. |

**Switching to Postgres**

1. Create an empty database and a user that owns it (psql or pgAdmin):
   ```sql
   CREATE USER perfagent WITH PASSWORD 'choose-a-password';
   CREATE DATABASE perfagent OWNER perfagent;
   ```
2. Add the URL to `.env` (URL-encode special characters in the password, e.g. `@` → `%40`):
   ```
   DATABASE_URL=postgresql://perfagent:choose-a-password@localhost:5432/perfagent
   ```
3. Run `uv sync`, then start the app. It creates every table on first start — there is
   nothing to run by hand. Postgres starts empty; data in an existing `perfagent.db` is not copied.
4. Check it: open `/api/health` — it shows `"backend": "postgresql"` and
   `"schema_up_to_date": true`.

To go back to SQLite, remove `DATABASE_URL`.

**What is handled for you on Postgres**

- Timestamps are stored as UTC whatever the server's time zone is.
- Text longer than its column is trimmed instead of failing the request (Postgres enforces
  lengths; SQLite never did), and NUL bytes are removed.
- Connections are pooled (`DATABASE_POOL_SIZE`, default 5) and checked before use, so a
  database restart does not break the app.
- Chat conversations are stored in the same Postgres database (LangGraph's own tables).
  `CHAT_CHECKPOINT_DB` overrides where they go.
- The password is never logged or shown.

**Changing the schema (developers)**

Tables are managed by Alembic migrations in `src/perfagent/db/migrations/`. The app applies
them on start-up; a database created before migrations existed is adopted as it is.
When you change a model in `db/models.py`, write the migration:

```bash
uv run alembic revision --autogenerate -m "add X to Y"
```

Review the generated file and commit it. A test fails if the models and migrations disagree.

**Running the test suite against Postgres**

```bash
# PowerShell:  $env:PERFAGENT_TEST_DATABASE_URL="postgresql://user:password@localhost:5432/perfagent_test"
PERFAGENT_TEST_DATABASE_URL=postgresql://user:password@localhost:5432/perfagent_test uv run pytest -q -n auto
```

Use a separate, empty database for this. Each test gets its own schema, removed at the end.

---

## API reference

Interactive docs are at **`/docs`** (and the raw OpenAPI file at `/openapi.json`). Every
endpoint is documented — what it does, what it returns — and sorted into groups:

| Group | What is in it |
|---|---|
| Conversation | The multi-turn planning chat |
| Planning | Draft a plan, import endpoints, saved plans, load shape, suggested checks |
| Request data | Data file upload, field sources, request preview |
| Scripts | Generate, upload, download, validate, pre-flight |
| Runs | Start, watch, stop, logs |
| Reports & history | Report, download, saved reports, trend |
| SLA profiles | Saved pass/fail rule sets |
| Git · Jenkins · Integrations | Save/import tests, run in Jenkins, remembered details |
| Observability | Audit log, AI usage, AI call traces |
| System | Health, supported tools |

Each endpoint also carries an **access level**, published in the OpenAPI file as `x-access`
(and `x-uses-ai` for calls that spend tokens):

| Level | Meaning |
|---|---|
| `read` | Only reads stored data. |
| `write` | Creates or changes stored data. |
| `run` | Sends real requests or load to the system under test. |
| `integrate` | Talks to Git or Jenkins with credentials supplied in the call. |

The agent does not enforce these itself — sign-in and permissions belong to the hub that
hosts it — but a gateway or a role system can read them to decide who may call what.
All of this lives in one file, `src/perfagent/api/docs.py`; a test fails if an endpoint is
added without documenting it there.

---

## Running the tests

The suite mocks the LLM and uses local fixtures. Tests that exercise k6 directly require an available binary or skip when it is unavailable:

```bash
uv run pytest -q
```

For a faster local run, execute the suite in parallel (the Git/Jenkins tests shell out to
real `git`, which is slower on Windows):

```bash
uv run pytest -q -n auto            # needs pytest-xdist
uv run pytest -q -k "not git"       # skip the slow Git integration tests
```

A few tests exercise POSIX-only behaviour (symlinks, `sh`) and are **skipped on Windows**;
they run in full on Linux/macOS CI.

Lint: `uv run ruff check src/ tests/`

---

## How it works

A concrete trace — you draft a plan:

1. Your endpoints (and any pasted collection) post to the API.
2. The API builds a **guarded** LLM provider — the guardrail **redacts** secrets/URLs from
   the *user* prompt before the model sees them (the system prompt is left intact).
3. The planner asks the model for a `LoadModel`, then **deterministic code takes over**: it
   forces the target URL, applies the chosen load profile, collapses duplicate journeys,
   sanity-fixes thresholds, auto-adds the auth header when a token is captured, and
   **restores your real request bodies** (the model only ever saw redacted ones).
4. The API returns the plan + a **grounding score** + the **redaction summary** + token usage.
5. You approve → the k6 script is rendered deterministically (data + headers + correlation +
   dynamic generators + assertions + TLS). You can edit it before running.
6. You run → k6 launches, the aggregator computes metrics (counting failed assertions as
   errors), the browser polls live metrics and **run logs**.
7. On finish → the API computes the **verdict**, **diagnosis**, and **baseline comparison**,
   writes a **citation-checked** narrative, and **saves the full report** (checks + logs
   included). Every consequential action (and its token cost) is audited.

---

## Data guardrails

A guardrail layer wraps **every** LLM call (via the provider interface) — there is no path to
the model that bypasses it. Only the **user** prompt (which carries user data) is redacted;
the fixed system prompt is left intact.

| Category | Handling |
|---|---|
| Emails, passwords, tokens, JWTs, cards (Luhn), SSNs, inline secrets | one-way redaction |
| URL query secrets (`?token=…`) | one-way redaction |
| URL hostnames, internal hosts, private IPs | reversible (restored in reports) |
| `${placeholder}` / `{{var}}` template references | preserved (not treated as secrets) |

The same guardrail protects **✨ Suggest checks from a response**: the pasted response is
redacted before the AI sees it. Only redaction **counts** are surfaced — never raw values. A
standalone `verify_guardrails.py` script and a `GUARDRAIL_DEBUG=1` mode (logs the *redacted*
prompt) let you confirm nothing sensitive reaches the AI before testing real endpoints.

---

## AI evaluation

- **Plan grounding** — only supplied endpoints are used, weights/think-times valid, within
  guard rails → *"✅ Plan grounded — 6/6 checks passed."*
- **Report citation** — every number in the narrative must trace to a real computed metric;
  fabricated figures are flagged (URLs and timestamps ignored) → *"✅ Report verified."*

---

## Observability — logging, audit & tokens

- **Structured logging** (structlog) — readable on the console, JSON in `logs/perfagent.log`;
  records workflow steps and counts, never secrets or bodies.
- **Run logs** — k6's own output (threshold crossings, the checks summary, and your script's
  `console.*` messages) is streamed live during a run and **saved with the report** for later.
- **Audit trail** — a durable record of consequential actions (plan created/approved, script
  generated, **run started** with target + peak VUs, **run finished** with verdict, Git push,
  Git import), shown as an **Activity log** in the UI and at `GET /api/audit`.
- **Token usage** — every AI call's tokens + rough cost are captured, shown as a **session
  total chip** in the top bar and **per-action** in the activity log.
- **AI-call tracing** — each real LLM call recorded with step · model · tokens · **latency** ·
  status, shown in a **Traces** view (`GET /api/traces`) for debugging the AI steps.

---

## Architecture

The React workspace calls the FastAPI JSON API. `LoadModel` is the shared test specification.
Approval saves or reuses a script version with frozen execution inputs. The runner
streams k6 events into the aggregator. The analysis layer computes threshold outcomes
and baseline changes, then saves the report for the dashboard and standalone HTML export.

```mermaid
flowchart LR
    UI["React workspace"] --> API["FastAPI JSON API"]
    API --> PLAN["Planning and imports"]
    PLAN --> MODEL["LoadModel"]
    MODEL --> APPROVE["Review and approve"]
    APPROVE --> GEN["Script renderer and frozen inputs"]
    GEN --> VERIFY["Verification"]
    GEN --> RUN["k6 runner"]
    RUN --> METRICS["Metrics aggregation and verdict"]
    METRICS --> REPORT["Saved report and HTML export"]
    API <--> DB[("SQLite or PostgreSQL")]
    REPORT --> DB
    DB --> DASH["Dashboard and history"]
    PLAN -.-> LLM["Guarded AI provider"]
    REPORT -.-> LLM
```

The UI also supports importing existing k6 scripts and recovering saved reports after a server restart.
Local and managed access have different deployment requirements. Managed gateway checks apply at the
workspace boundary. Per-project authorization and PostgreSQL row-level security remain hosted deployment work.

---

## Project layout

| Path | Responsibility |
|---|---|
| `config.py` | Settings + secrets from `.env` (incl. `log_level`, `guardrail_debug`, Git/Jenkins allow-lists). |
| `contracts/load_model.py` | Core model: `LoadModel`, `Scenario`, `Step`, `Extract`, `Assertion`, `LoadProfile`, `Threshold`, `DataFile`, `headers`, `environment`, `insecure_tls`. |
| `chat_intent.py` | Chat → structured plan intent (plain-English describe). |
| `chat/` | Conversation mode: `draft.py` (per-turn schema, deterministic merge + readiness), `prompts.py`, `graph.py` (the LangGraph graph), `planning.py` (hand-off to the planner), `service.py` (sessions, secret masking, checkpointing). |
| `plan_summary.py` | Shared plan rationale / guardrail / token-usage summaries. |
| `dynamize.py` | AI "add dynamic data" — assign generators/CSV columns to a body's fields. |
| `check_suggest.py` | AI "suggest checks from a response" — propose assertions from a pasted response. |
| `importers/endpoints.py` | Import endpoints from OpenAPI/Swagger (JSON+YAML), Postman, HAR. |
| `guardrails/` | Redaction engine + output scrubbing around every LLM call. |
| `evaluation/` | Plan-grounding and report-citation checks. |
| `usage.py` · `tracing.py` | Token-usage extraction + rough cost estimate; per-AI-call traces. |
| `providers/` | OpenAI / Anthropic behind one interface (Instructor), wrapped by guardrails. |
| `planner/` | Endpoints → AI-drafted LoadModel; deterministic controls (target, profile, sanity, auto-correlation, real-body restore). |
| `generator/k6_renderer.py` · `k6_data.py` · `k6_corr.py` · `generators.py` · `templates/` | LoadModel → k6 script (data, headers, correlation, dynamic generators, assertions, logging). |
| `generator/locust_renderer.py` · `jmeter_renderer.py` · `gatling_renderer.py` | Locust, JMeter (.jmx), and Gatling (.scala) renderers. |
| `gitexport/` | Build a CI-ready k6 framework (`framework.py`), publish to Git (`publisher.py`), import back (`importer.py`), file templates (`templates.py`). |
| `ci/jenkins.py` | Jenkins trigger / status / stop / job set-up. |
| `integrations.py` | Saved (non-secret) Git & Jenkins details per plan. |
| `preflight.py` | One request per endpoint → status report (no load). |
| `runner/k6_runner.py` · `runner/validator.py` · `runner/k6_binary.py` | Launch & stream k6 (metrics + logs); validate a script via `k6 inspect`; find or auto-download k6. |
| `stats/aggregator.py` | Deterministic metric aggregation (percentiles, error rate, RPS; failed checks count as errors). |
| `analyzer/verdict.py` · `diagnostics.py` · `baseline.py` · `narrator.py` · `report.py` | Verdict (fail-closed), diagnosis, regression compare, AI narrative, HTML report. |
| `logging_config.py` · `audit.py` | Structured logging and the audit trail. |
| `api/docs.py` | Every API endpoint documented in one place: group, summary, access level, AI use. |
| `request_data.py` | Where each request value comes from (fixed / data file / generated), sample values, and the request preview. |
| `db/connection.py` · `db/migrate.py` · `db/migrations/` | Database URL handling (SQLite / Postgres), write-time safety, and Alembic migrations applied on start-up. |
| `db/models.py` | SQLAlchemy models: plans, scripts, data files, run results (+ saved reports & logs), audit, SLA profiles, traces, integration settings, chat sessions. |
| `api/app.py` + `api/*_routes.py` | FastAPI app: REST API + serves the UI; export / git-import / integration / jenkins / chat routes. |
| `web/index.html` | The guided wizard UI (conversation + quick + manual modes, report dashboard, git/Jenkins panels, single file). |
| `sample_target/app.py` | A mock website to test against safely. |

**Tests** cover the schema, generators (incl. realistic + Postman syntax), planner & profiles
& body-restore, runner/stats/validator, analyzer (fail-closed verdict, diagnostics, baseline),
API, guardrails (URL + placeholder), evaluation, data, importers, headers/pre-flight,
correlation (JSON/header/cookie/regex/array), assertions (incl. failed checks counting as
errors), suggested checks & environment/TLS, chat intent, dynamize, console logging, audit,
token usage, SLA profiles, trend, JMeter/Gatling, tracing, GraphQL, k6 auto-provisioning, and
the Git export / import / Jenkins / integrations features.

---

## Safety notes

> [!WARNING]
> **Only run load against systems you own or have explicit written permission to test.**
> Generating load against systems you don't control can cause outages and may be illegal.

- The human approval gate sits **before** any load is fired — always review the plan first.
- Start with low user counts and short durations on any new target, then scale up.
- Sensitive data is redacted before it reaches the LLM; extend detectors in
  `guardrails/redaction.py` for your environment before pointing at production-adjacent data.
- **Skip TLS verification** is for test/dev hosts only — never enable it against production.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Run logs show garbled characters (`â–ˆ`, `âœ"`) | Update to the current runner — k6 output is now decoded as UTF-8. |
| A run PASSes even though the API returned an error payload | Add an assertion (e.g. **does NOT contain** the error string, or a **JSON field** check). Failed assertions count as errors. |
| Save to Git: "folder already exists and was not created by PerfAgent" | Choose a new framework name; PerfAgent never writes into folders it didn't create. |
| Save to Git / Import: "git ... failed: Authentication failed" | Check the token has access to that repository (push rights for Save to Git). |
| Jenkins log: `Cannot run program "sh"` | The job ran an old Jenkinsfile on a Windows agent. Push the test again with **Save to Git** (the new Jenkinsfile supports Windows), then run again. |
| Run in Jenkins: "doesn't accept parameters yet" | Run the job once in Jenkins, or use **Set up Jenkins job**. |
| Run in Jenkins: "rejected the user name or API token" | Use a Jenkins **API token** (not your password) for that user. |
| Jenkins build fails with "Could not find credentials entry with ID 'PERF_HEADER_…'" | Add that Secret text credential in Jenkins. |
| "could not download k6" | The machine can't reach github.com. Set `HTTPS_PROXY`, or point `PERFAGENT_K6_PATH` at a k6 binary. |
| "no prebuilt k6 for this platform" | Unusual OS/CPU — install k6 manually and set `PERFAGENT_K6_PATH`. |
| "OPENAI_API_KEY is not set" | Fill the key in `.env` and restart the app. |
| Run shows 0 requests / "Run error" | The target isn't running, or the URL is wrong. Start the target and retry. |
| A step shows "values with no source" | A `${name}` in its body is not a data-file column, not generated and not captured. Open the step and pick a source, or upload a file with that column. |
| The run stopped with "the data file ran out of rows" | Rows are set to *Each row once* and there were fewer rows than requests. Add rows, shorten the test, or let rows repeat. |
| Conversation tab is missing | `CHAT_CONVERSATION_ENABLED` is `false`, or dependencies are stale — run `uv sync`. |
| Imported a spec but no endpoints | Confirm it's valid OpenAPI (JSON/YAML), a Postman collection, or a `.har`. |
| `/me` (or a protected call) is 401 in pre-flight | Expected — pre-flight hits endpoints alone; correlation flows the token only in a full run. |
| `table ... already exists` on startup | Delete the SQLite DB once (new tables/columns were added) and restart. |
| Tests fail on import | Run `uv sync` again; make sure you're in the project `.venv`. |

---

## Roadmap

**✅ Working today**
**Conversational chat (multi-turn, saved, LangGraph)** · quick describe or form input · import (OpenAPI/Swagger JSON+YAML, Postman, HAR, **and from Git**) · AI
planning with an editable form & plain-English summary · guardrails (+ verify script & debug
mode) · AI evaluation · correlation (JSON/header/cookie/regex/array, auto-set-up) ·
**assertions (contains / not-contains / status / JSON compare / response-time) with ✨
suggest-checks-from-a-response** · **dynamic data (generators + CSV + AI "add dynamic data",
Postman `{{var}}` syntax)** · custom headers · **environment & TLS options** · test types
(ramp/spike/soak/stress) · **GraphQL** · multi-tool generation (k6/Locust/JMeter/Gatling) ·
pre-flight · script validation · **editable script** · live monitoring + chart + **run logs** ·
diagnosis engine · fail-closed verdict · baseline/regression · **report dashboard + response
checks + saved runs & logs history** · **Save to Git (GitHub/Jenkins/Azure/GitLab pipelines) ·
Import from Git · Run in Jenkins** · run-an-existing-script · logging, audit, token usage &
AI traces · modern UI with inline guidance.

**🔭 Planned next**
- **More protocols** — gRPC (needs the k6 gRPC extension + `.proto`) and WebSocket streaming.
- **Live runners for JMeter / Gatling** (scripts generate today; a live runner is k6-only).
- **Autonomy** — extend the conversation graph so the agent sequences generate → run → diagnose → report itself, with approval as an interrupt.
- **Scheduled & CI-triggered runs**; trend alerting on regression.
- **Reliability for the hub** — durable/concurrent run state, load workers, target allow-list & VU caps.

---

<div align="center">
<sub>Built with FastAPI · k6 · Pydantic · Instructor · LangGraph · OpenAI / Anthropic · SQLAlchemy · structlog</sub>
</div>
