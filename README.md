# AI Performance Testing Agent

An AI agent that **plans, generates, runs, and reports on performance tests** — all
from one web UI. You describe a target and its endpoints; the agent drafts a test
plan, you review and approve it, and the agent generates a runnable load-test
script, runs it with live monitoring, and produces a stakeholder-ready report.

> **Guiding principle:** the AI *drafts and narrates*; deterministic code *owns
> every number and the pass/fail verdict*; a *human approves* before any load is
> fired. Sensitive data is *redacted before it ever reaches the AI*. This is what
> makes the tool safe to point at real infrastructure.

---

## Table of contents

- [What it does](#what-it-does)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the app](#running-the-app)
- [Running the tests](#running-the-tests)
- [Data guardrails](#data-guardrails)
- [Architecture](#architecture)
- [Every file explained](#every-file-explained)
- [How a request flows through the system](#how-a-request-flows-through-the-system)
- [Safety notes](#safety-notes)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

---

## What it does

The full loop, in one browser app:

1. **Plan** — the AI drafts a structured test plan (a *LoadModel*) from your
   endpoints: realistic user journeys, traffic weights, think times, thresholds.
2. **Approve** — you review and edit the plan, then approve it. Nothing runs without this.
3. **Generate** — a deterministic renderer turns the plan into a runnable **k6**
   script (Locust also supported). No LLM touches the script — the same plan always
   produces the same script.
4. **Run + monitor** — the agent launches k6 and streams live metrics into the
   browser (requests, RPS, error rate, p95/p99 latency, per-endpoint breakdown).
5. **Report** — a deterministic pass/fail verdict against the thresholds, plus an
   AI-written plain-English summary, downloadable as a self-contained HTML report.

Sensitive data (emails, passwords, tokens, cards, internal hosts, URL secrets) is
**redacted before anything is sent to the AI** — see [Data guardrails](#data-guardrails).

The load-model shape (ramp up → steady → ramp down) and all metrics/verdicts are
computed by code. The AI is only involved at two points: drafting the plan and
writing the report narrative — and in both it must use the real, computed numbers.

---

## Prerequisites

Install these on your system before running the project.

| Requirement | Why | How to check | Where to get it |
|---|---|---|---|
| **Python 3.11+** | The whole service is Python | `python --version` | https://www.python.org/downloads/ |
| **uv** *(or plain pip)* | Installs dependencies. uv is recommended; pip works too (see Setup) | `uv --version` | https://docs.astral.sh/uv/getting-started/installation/ |
| **k6** | Runs the load tests (needed only for the Run step) | `k6 version` | https://grafana.com/docs/k6/latest/set-up/install-k6/ |
| **Git** | To clone / push the repo | `git --version` | https://git-scm.com/downloads |
| **An LLM API key** | For AI planning + report narration | — | OpenAI: https://platform.openai.com/ · Anthropic: https://console.anthropic.com/ |

Notes:

- **You do NOT need k6** just to plan and generate scripts — only to actually *run*
  them from the UI. You can also download a generated script and run it on any
  machine that has k6.
- **You do NOT need an API key** to run the app skeleton or the test suite — the
  tests mock the LLM. A key is only needed for the live "Draft plan with AI" and the
  AI-written report narrative.
- **Set a spend cap** on your OpenAI/Anthropic account before using the AI features.
- Everything is cross-platform (Windows, macOS, Linux). Commands below show Windows
  where it differs (`copy` vs `cp`).

---

## Setup

You can install with **uv** (recommended, faster) or plain **pip**. Use whichever
your team prefers — both produce the same environment.

### Option A — using uv (recommended)

    git clone <your-repo-url>
    cd perfagent
    uv sync                       # installs everything, creates .venv automatically

### Option B — using pip + venv (no uv needed)

    git clone <your-repo-url>
    cd perfagent

    python -m venv .venv
    .venv\Scripts\activate         # Windows
    # source .venv/bin/activate     # macOS / Linux

    pip install -r requirements.txt              # runtime only
    # pip install -r requirements.txt -r requirements-dev.txt   # + tests & linting

### Then (both options) — create your env file

    copy .env.example .env        # Windows
    # cp .env.example .env        # macOS / Linux

Open `.env` and fill in your provider and key:

    LLM_PROVIDER=openai           # or "anthropic"
    OPENAI_API_KEY=sk-...         # fill in whichever provider you chose
    ANTHROPIC_API_KEY=
    OPENAI_MODEL=gpt-4o-2024-11-20
    ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
    MAX_TOKENS=4096

`.env` is git-ignored, so your key is never committed.

> **Which files pin dependencies?** `pyproject.toml` + `uv.lock` are the source of
> truth (used by uv). `requirements.txt` (runtime) and `requirements-dev.txt` (tests
> + lint) are provided for pip users and for deployment tooling that expects them.

---

## Running the app

**Terminal 1 — start the agent (the web app + API):**

    uv run uvicorn perfagent.api.app:app --reload --port 8080

Open **http://127.0.0.1:8080** in your browser.

> Using pip instead of uv? Activate your venv first, then drop the `uv run` prefix from every command below — e.g. `uvicorn perfagent.api.app:app --reload --port 8080` and `pytest -q`.

**Terminal 2 — start the built-in mock target (something safe to test against):**

    uv run python -m perfagent.sample_target.app     # serves http://127.0.0.1:8000

**In the browser:**

1. Target `http://127.0.0.1:8000`, keep the pre-filled endpoints.
2. Set Max users (e.g. 20) and Duration (e.g. 60s).
3. Click **Draft plan with AI** — the AI proposes a plan. A guardrail badge shows how
   many sensitive values were redacted before the prompt was sent to the AI.
4. Review/edit it, then **Approve & generate script** — a k6 script appears.
5. Click **Run & monitor live** — watch metrics stream in.
6. When it finishes, the **Report** section shows a verdict + summary you can download.

**Running a generated script yourself (optional):** download it from the UI, then

    k6 run -e BASE_URL=http://127.0.0.1:8000 loadtest.js

---

## Running the tests

The suite mocks the LLM, so it needs **no API key** and makes **no paid calls**:

    uv run pytest -q

You should see all tests pass. Lint with:

    uv run ruff check src/ tests/

---

## Data guardrails

Because planning and reporting send data to an external LLM, a guardrail layer sits
around **every** LLM call and protects sensitive data. It is wired into the provider
interface (`providers/__init__.py` wraps the provider in `GuardedProvider`), so both
the planner and the reporter are covered automatically — there is no path to the LLM
that bypasses it.

**Input redaction — before the prompt is sent to the AI:**

| Category | Example | Handling |
|---|---|---|
| Emails | `jane@acme.com` | one-way `<EMAIL_REDACTED>` |
| Passwords / tokens / keys (by field name or inline `key=value`) | `"password": "..."`, `token=...` | one-way `<FIELD_REDACTED>` |
| JWTs | `eyJ...` | one-way `<JWT_REDACTED>` |
| Credit-card numbers (Luhn-validated) | `4242 4242 4242 4242` | one-way `<CARD_REDACTED>` |
| SSNs | `123-45-6789` | one-way `<SSN_REDACTED>` |
| URL query secrets | `?token=abc&api_key=xyz` | one-way `<QUERY_SECRET_REDACTED>` |
| URL hostnames | `https://api.acme.com/login` | reversible `<HOST_1>` (path kept) |
| Internal hosts / private IPs | `payments.internal`, `10.0.4.21` | reversible placeholder |

**Two kinds of masking:**
- **One-way (secrets):** replaced with a fixed placeholder and *never* restored — the
  LLM never sees them and neither does anything downstream.
- **Reversible (identifiers):** hostnames and private IPs get stable placeholders that
  are mapped back *after* the LLM responds, so reports read naturally with real names.

**URL handling specifically:** the host is masked (reversibly) and any secret in the
query string is stripped (one-way), but the **path is kept** — the AI needs paths
(`/login`, `/checkout`) to group endpoints into journeys. The real target URL is also
forced by code in the planner, so the LLM never controls what actually gets hit.

**Output scrubbing — after the AI responds:** the model's text output is scanned and
any secret-looking content is removed (defence against prompt-injection leaks).

**Visible in the UI:** after drafting a plan, a badge shows e.g.
*"🛡 2 sensitive values redacted before sending to the AI (1 email, 1 secret)"*. Only
counts are ever surfaced or logged — never the raw values.

> Redaction uses pattern detectors covering the common high-risk cases. For a specific
> environment you can extend the detector list in `guardrails/redaction.py` (e.g. add
> company-specific ID formats).

---

## AI evaluation

Guardrails protect what goes *into* the AI; the evaluation harness verifies what comes
*out* of it — deterministically, against ground truth, never against "does it sound good."
It answers the question "how do we know the AI did a good job?"

**Plan grounding (`evaluation/plan_eval.py`)** — checks a drafted plan against the
endpoints that were actually supplied:

- no invented endpoints (the AI can't make up a path that wasn't given)
- target URL matches the request
- has scenarios, each with steps; weights positive; think times valid
- stays within the requested guard rails (max users, duration)

Produces a score like *grounded: true, 6/6 checks passed*.

**Report citation (`evaluation/report_eval.py`)** — the key check: every number in the
AI's narrative must trace to a real computed metric. A figure in the text that isn't in
the actual results is a hallucination and is flagged. Produces *grounded: true, N numbers
in text, 0 hallucinated*.

Because the AI only *proposes* a plan (a human approves) and only *narrates* a report
(code computes the numbers and the verdict), it cannot produce a wrong result — only a
wrong draft, which these checks catch.

---

## Architecture

![Architecture](docs/architecture.png)

*The engine at a glance: real-data inputs → an AI-proposed, human-approved plan (the LoadModel) → deterministic execution → an AI-narrated report, with a feedback loop, data guardrails on every LLM call, and AI evaluation of the output.*

A text version of the same flow (renders on GitHub):

The system is a pipeline of stages connected by a shared contract (the `LoadModel`).
The AI is involved in only two places — drafting the plan and writing the report
narrative — and both go through the data guardrails. Everything else is deterministic
code, and a human approves before any load is fired.

```mermaid
flowchart TD
    IN([Input: target URL + endpoints, typed in the UI])

    PLAN["1 · Plan<br/><small>AI drafts journeys, weights, thresholds</small><br/><code>planner/</code>"]
    LM["LoadModel — the contract<br/><small>scenarios · load profile · thresholds</small><br/><code>contracts/</code>"]
    APPROVE["2 · Approve — human gate<br/><small>review & edit; nothing runs without a yes</small><br/><code>web/</code>"]
    GEN["3 · Generate — deterministic<br/><small>LoadModel to runnable k6 script</small><br/><code>generator/</code>"]
    RUN["4 · Run + monitor<br/><small>launch k6, aggregate live metrics</small><br/><code>runner/ · stats/</code>"]
    REPORT["5 · Report<br/><small>code: PASS/FAIL verdict · AI: narrates to HTML report</small><br/><code>analyzer/</code>"]
    OUT([Output: live dashboard + downloadable report])

    IN --> PLAN --> LM --> APPROVE --> GEN --> RUN --> REPORT --> OUT

    GUARD["Data guardrails — wrap every LLM call<br/><small>redact input · scrub output</small><br/><code>guardrails/</code>"]
    GUARD -. protects .-> PLAN
    GUARD -. protects .-> REPORT

    CROSS["Cross-cutting — supports every stage<br/><small>api/ FastAPI + UI · db/ persistence + lineage · providers/ OpenAI + Claude · config.py secrets · sample_target/ mock site</small>"]

    classDef ai    fill:#EEEDFE,stroke:#534AB7,color:#26215C;
    classDef code  fill:#E1F5EE,stroke:#0F6E56,color:#04342C;
    classDef gate  fill:#FAEEDA,stroke:#854F0B,color:#412402;
    classDef io    fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A;
    classDef cross fill:#F1EFE8,stroke:#B4B2A9,color:#2C2C2A;

    class PLAN ai;
    class LM,GEN,RUN,REPORT code;
    class APPROVE gate;
    class GUARD gate;
    class IN,OUT io;
    class CROSS cross;
```

**Who owns what (the trust boundary):**

| Colour | Owner | Stages |
|--------|-------|--------|
| Purple | **AI drafts** | Plan (and the report *narrative*) |
| Teal | **Code owns** | LoadModel, Generate, Run, metrics, verdict |
| Amber | **Human gate / guardrails** | Approve — before any load fires; redact — before any LLM call |

The AI only touches the first stage (drafting the plan) and the wording of the final
report. Every number, the generated script, and the pass/fail verdict are produced by
deterministic code. A human approves before any load is fired, and the guardrails
redact sensitive data before it reaches the AI.

---

## Every file explained

### Project root

| File | What it is |
|---|---|
| `pyproject.toml` | Project metadata + dependencies (used by `uv`). Also ruff/pytest config. |
| `uv.lock` | Exact pinned versions of every dependency, so installs are reproducible. |
| `requirements.txt` | Runtime dependencies for pip users / deployment (mirrors pyproject). |
| `requirements-dev.txt` | Test + lint dependencies for pip users. |
| `.env.example` | Template for environment variables. Copy to `.env` and fill in keys. |
| `.env` | Your real secrets (git-ignored — never committed). |
| `.gitignore` | Tells git to skip `.env`, the database, caches, the virtualenv, etc. |
| `README.md` | This file. |

### `src/perfagent/` — the service

| File | Responsibility |
|---|---|
| `__init__.py` | Marks the package; holds the version string. |
| `config.py` | Loads settings + secrets from `.env` via pydantic-settings. The ONLY place env vars are read. |

### `src/perfagent/contracts/` — the shared contract

| File | Responsibility |
|---|---|
| `load_model.py` | **The core data model.** Defines `LoadModel` (a whole test plan) and its parts: `Scenario` (a user journey), `Step` (one request), `ThinkTime`, `LoadProfile` + `Stage` (how load ramps over time), `Threshold` (pass/fail bounds), `HttpMethod`. All validated by Pydantic — this validation is the trust boundary. |
| `artifacts.py` | Wraps outputs with identity + lineage: `PlanArtifact` (a LoadModel with an id) and `ScriptArtifact` (a generated script that points back to the plan it came from). |
| `__init__.py` | Re-exports the above for easy importing. |

### `src/perfagent/guardrails/` — data protection around the LLM

| File | Responsibility |
|---|---|
| `redaction.py` | The redaction engine: pattern detectors for emails, secrets, JWTs, cards, SSNs, URL hosts and query secrets, internal hosts and private IPs. One-way masking for secrets, reversible for identifiers. |
| `output.py` | Scrubs the LLM's response for any secret-looking content it may have produced. |
| `__init__.py` | `GuardedProvider` — wraps any provider; redacts prompts before sending and scrubs/restores the response. Exposes `last_redaction_counts` for the UI badge. |

### `src/perfagent/evaluation/` — AI quality checks

| File | Responsibility |
|---|---|
| `plan_eval.py` | Deterministic grounding checks on a drafted plan (no invented endpoints, valid weights/think-times, within guard rails). Returns a score. |
| `report_eval.py` | Checks the AI report narrative cites only real computed numbers — catches hallucinated figures. |
| `__init__.py` | Re-exports `evaluate_plan`, `evaluate_report`. |

### `src/perfagent/providers/` — the LLM layer

| File | Responsibility |
|---|---|
| `base.py` | Defines `LLMProvider`, the single interface the rest of the code calls. Nothing outside this folder imports the OpenAI/Anthropic SDKs. |
| `openai_provider.py` | OpenAI implementation, using Instructor to return validated Pydantic objects. |
| `anthropic_provider.py` | Anthropic (Claude) implementation, same interface. |
| `__init__.py` | `build_provider()` — reads config, builds the provider, and wraps it in `GuardedProvider` so every LLM call is guarded. |

### `src/perfagent/planner/` — Stage 1: Plan

| File | Responsibility |
|---|---|
| `spec.py` | `EndpointSpec` and `PlanRequest` — the Planner's input (endpoints + target + goal + guard rails). |
| `prompts.py` | The system + user prompts that instruct the AI how to draft a plan. |
| `profile.py` | **Deterministic** load-profile builder: turns "peak users + duration" into a proper ramp-up → steady → ramp-down shape. Code owns this, not the AI. |
| `planner.py` | `draft_plan()` — asks the provider for a LoadModel, then applies deterministic controls (forces the target URL, replaces the load-profile shape with `profile.py`'s output). |
| `__init__.py` | Re-exports `draft_plan`, `EndpointSpec`, `PlanRequest`. |

### `src/perfagent/generator/` — Stage 3: Generate

| File | Responsibility |
|---|---|
| `k6_renderer.py` | Turns a LoadModel into a runnable **k6** script (the primary tool). Pure templating + arithmetic; no LLM. |
| `locust_renderer.py` | Same, for Locust (alternative tool). |
| `templates/k6.js.j2` | The Jinja2 template for k6 scripts. |
| `templates/locust.py.j2` | The Jinja2 template for Locust scripts. |
| `__init__.py` | `render()` / `generate_script()` — dispatches to the right renderer by tool name. Adding a new tool = one new renderer here. |

### `src/perfagent/runner/` — Stage 4: Run

| File | Responsibility |
|---|---|
| `k6_runner.py` | Launches k6 as a subprocess with JSON output, parses the stream, tracks each run's live state in memory, and lets a run be stopped. Falls back to a clear error if k6 isn't installed. |
| `__init__.py` | Re-exports the runner functions. |

### `src/perfagent/stats/` — deterministic metrics

| File | Responsibility |
|---|---|
| `aggregator.py` | Consumes k6's raw metric points and computes the numbers the UI shows: request counts, error rate, RPS, and latency percentiles (via NumPy), including per-endpoint. **Every number comes from here, never the AI.** |
| `__init__.py` | Re-exports `Aggregator`. |

### `src/perfagent/analyzer/` — Stage 5: Report

| File | Responsibility |
|---|---|
| `verdict.py` | **Deterministic** PASS/FAIL: compares the run's actual metrics against the plan's thresholds. Code decides the verdict, never the AI. |
| `narrator.py` | Produces a plain-English `Narrative` from the computed numbers + verdict, using the LLM — with a deterministic template fallback if no key is set, so a report can always be produced. |
| `report.py` | Renders everything into a self-contained, downloadable HTML report. |
| `__init__.py` | Re-exports `evaluate`, `narrate`, `Narrative`, `render_report_html`. |

### `src/perfagent/db/` — persistence

| File | Responsibility |
|---|---|
| `models.py` | SQLAlchemy models `PlanRow` and `ScriptRow` (script points back to its plan = lineage), plus the engine/session setup. Uses SQLite by default. |
| `__init__.py` | Re-exports the models and session helpers. |

### `src/perfagent/api/` — the web service

| File | Responsibility |
|---|---|
| `app.py` | The FastAPI application. Serves the UI at `/` and exposes the REST API: plan, generate, list/get plans, download script, run, poll run status, stop run, and the report endpoints. The plan response includes the guardrail redaction summary for the UI badge. |
| `__init__.py` | Marks the package. |

### `src/perfagent/web/` — the UI

| File | Responsibility |
|---|---|
| `index.html` | The entire browser UI in one file (HTML + CSS + JS). Talks to the API. Sections: describe test, review/approve plan (with the guardrail badge), generated script, live monitor, stakeholder report, saved plans. |

### `src/perfagent/sample_target/` — a safe test target

| File | Responsibility |
|---|---|
| `app.py` | A tiny mock website (`/products`, `/login`, `/cart`, `/checkout`) using only the Python standard library, so you always have something safe to load-test. |
| `__init__.py` | Marks the package. |

### `tests/` — the test suite (all mock the LLM)

| File | What it checks |
|---|---|
| `test_load_model.py` | The LoadModel schema validates correctly (bad URLs, paths, think times rejected). |
| `test_generator.py` | The generator dispatch + Locust rendering, determinism, lineage. |
| `test_k6_renderer.py` | k6 script generation: valid output, weighted VU split, thresholds, no zero-user scenarios. |
| `test_planner.py` | The Planner builds prompts, applies deterministic controls, produces valid plans (with a fake provider). |
| `test_profile.py` | The deterministic load-profile builder (ramp/spike/soak/stress shapes). |
| `test_runner.py` | The metrics aggregator and the runner's guard behavior (missing k6, wrong tool). |
| `test_analyzer.py` | The deterministic verdict, the narration fallback, and HTML report rendering. |
| `test_api.py` | End-to-end API flow with a fake provider and a temp database. |
| `test_guardrails.py` | Redaction of emails, secrets, JWTs, cards, inline secrets; reversible hosts; output scrubbing; that the guarded provider never sends raw secrets. |
| `test_url_guardrails.py` | URL host masking (path kept, reversible) and URL query-string secret stripping (one-way). |
| `test_evaluation.py` | Plan grounding checks (catches invented endpoints, guard-rail breaches) and report citation checks (catches hallucinated numbers). |

---

## How a request flows through the system

A concrete example — you click "Draft plan with AI":

1. The browser (`web/index.html`) POSTs your endpoints to `/api/plan` in `api/app.py`.
2. `app.py` calls `providers.build_provider()` to get the guarded LLM, then
   `planner.draft_plan()`.
3. `planner.py` builds prompts (`prompts.py`). The `GuardedProvider` **redacts**
   the prompt (`guardrails/redaction.py`) before it reaches the model, then asks the
   provider for a `LoadModel` (validated by `contracts/load_model.py`), then forces
   the target URL and replaces the load-profile shape using `profile.py`.
4. `app.py` saves it via `db/models.py` and returns the plan JSON plus the redaction
   summary (for the badge) to the browser.
5. You review it and click approve+generate → `/api/plan/{id}/generate` →
   `generator/` renders a k6 script → saved with lineage → shown in the UI.
6. You click run → `/api/scripts/{id}/run` → `runner/k6_runner.py` launches k6;
   `stats/aggregator.py` computes live metrics; the browser polls `/api/runs/{id}`.
7. On finish → `/api/runs/{id}/report` → `analyzer/` computes the verdict
   (`verdict.py`), narrates it via the guarded provider (`narrator.py`), and can
   render the HTML (`report.py`) for download.

---

## Safety notes

- **Only run load against systems you own or have explicit written permission to
  test.** Generating load against systems you don't control can cause outages and may
  be illegal.
- The human approval gate sits *before* any load is fired — always review the plan
  and script first.
- Start with low user counts and short durations on any new target, then scale up.
- The tool never fires load on its own — a human clicks Run.
- Sensitive data is redacted before it reaches the LLM, but review the guardrail
  badge and extend the detectors for your environment before pointing it at
  production-adjacent data.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "k6 is not installed or not on PATH" | Install k6 and reopen the terminal. Check with `k6 version`. |
| "OPENAI_API_KEY is not set" (or ANTHROPIC) | Fill the key in `.env` and restart the app. |
| Plan step errors immediately | Wrong `LLM_PROVIDER` vs which key you filled in, or no spend left on the account. |
| The run shows 0 requests / "Run error" | The target isn't running. Start the mock target (or check your real target URL), then run again. |
| Generated script won't run in k6 | Regenerate it (older scripts from earlier versions may differ); ensure the file saved as UTF-8. |
| Tests fail on import | Run `uv sync` again; make sure you're using the project's `.venv`. |

---

## Roadmap

**Working today:** the full loop — plan, approve, generate (k6), run, live monitor,
report — via the web UI, backed by a database with lineage, with data guardrails on
every LLM call and an AI evaluation harness for plan grounding and report citation.

**Planned next:**
- Authentication / correlation (log in, capture tokens) — to test authenticated sites
- Discovery — crawl a site or ingest real traffic (HAR / traces) instead of typing endpoints
- Baseline comparison / regression detection across runs
- WebSockets for live monitoring; async task queue for concurrent runs
- PDF report export
- More tool renderers (JMeter, Gatling) and deeper Locust support
- Run persistence, multi-tenancy, tool-level auth, CI/CD integration (enterprise hardening)

---

## Design documents

See the `docs/` folder for the architecture, approach, reference-repo teardown, and
tech-stack decisions.