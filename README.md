# AI Performance Testing Agent

An AI agent that plans, generates, runs, and reports on performance tests — from a
web UI. You describe a target and its endpoints; the agent drafts a test plan, you
review and approve it, and the agent generates a runnable load-test script, runs it
with live monitoring, and produces a stakeholder-ready report.

**Guiding principle:** the AI *drafts and narrates*; deterministic code *owns every
number and the pass/fail verdict*; a *human approves* before any load is fired.

---

## What it does

The full loop, in one browser app:

1. **Plan** — the AI drafts a structured test plan (a *LoadModel*) from your endpoints:
   realistic user journeys, traffic weights, think times, and pass/fail thresholds.
2. **Approve** — you review and edit the plan, then approve it. Nothing runs without this.
3. **Generate** — a deterministic renderer turns the plan into a runnable **k6** script
   (Locust also supported). No LLM touches the script — same plan always yields the same script.
4. **Run + monitor** — the agent launches k6 and streams live metrics into the browser
   (requests, RPS, error rate, p95/p99 latency, per-endpoint breakdown).
5. **Report** — a deterministic pass/fail verdict against the thresholds, plus an
   AI-written plain-English summary, downloadable as a self-contained HTML report.

The load-model shape (ramp up -> steady -> ramp down) and all metrics/verdicts are
computed by code. The AI is only involved at two points: drafting the plan and
writing the report narrative — and it must use the real, computed numbers.

---

## Requirements

- **Python 3.11+**
- **uv** (dependency manager) — https://docs.astral.sh/uv/
- **k6** installed and on PATH — https://grafana.com/docs/k6/latest/set-up/install-k6/
  (only needed to actually *run* tests; planning and generating work without it)
- An **OpenAI** or **Anthropic** API key (only needed for AI planning/narration; the
  app runs and the test suite passes without one)

---

## Setup

    uv sync                     # install dependencies
    copy .env.example .env      # Windows  (cp on macOS/Linux)

Then edit `.env` and set your provider and key:

    LLM_PROVIDER=openai         # or "anthropic"
    OPENAI_API_KEY=sk-...       # fill in the one you use
    ANTHROPIC_API_KEY=

> Set a **spend cap** on your provider account before running — planning makes a
> real API call.

---

## Run the app

    uv run uvicorn perfagent.api.app:app --reload --port 8080

Open **http://127.0.0.1:8080** in your browser.

### Try it against the built-in mock target

The project ships a tiny mock API so you have something safe to test against. In a
second terminal:

    uv run python -m perfagent.sample_target.app     # serves http://127.0.0.1:8000

Then in the UI: keep the target `http://127.0.0.1:8000`, use the pre-filled
endpoints, click **Draft plan with AI** -> **Approve & generate script** ->
**Run & monitor live**. When it finishes, a **Report** section appears with the
verdict and a downloadable HTML report.

### Run a generated script yourself

You can also download the script and run it directly:

    k6 run -e BASE_URL=http://127.0.0.1:8000 loadtest.js

---

## Tests

The test suite mocks the LLM, so it needs **no API key** and makes **no paid calls**:

    uv run pytest -q

---

## How it is organised

One service, internally modular. Each stage is connected to the next only through
persisted artifacts, so any stage can run on its own.

    src/perfagent/
      contracts/       the LoadModel schema + artifacts (the contract every stage reads)
      providers/       OpenAI / Anthropic behind one interface (via Instructor)
      planner/         endpoints -> AI-drafted LoadModel (+ deterministic load-profile shape)
      generator/       LoadModel -> runnable script (k6 primary, Locust supported)
      runner/          launches k6 as a subprocess, streams output
      stats/           deterministic metric aggregation (percentiles, error rate, RPS)
      analyzer/        deterministic verdict + AI narrative + HTML report
      db/              SQLAlchemy models (plans + scripts, with lineage)
      api/             FastAPI app (REST API + serves the web UI)
      web/             the browser UI (single HTML file)
      sample_target/   mock API to develop and test against safely

**Stack:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic, Instructor (structured LLM
output), Jinja2 (script templating), NumPy (percentiles), OpenAI + Anthropic.

---

## Safety notes

- **Only run load against systems you own or have explicit permission to test.**
  Generating load against systems you don't control can cause outages and may be illegal.
- The human approval gate sits *before* any load is fired — review the plan and script
  before running.
- Start with low user counts and short durations on any new target, then scale up.

---

## Status and roadmap

**Working today:** the full loop — plan, approve, generate (k6), run, live monitor,
report — via the web UI, backed by a database with lineage.

**Not yet built (roadmap):**
- Authentication / correlation (log in, capture tokens) — needed for authenticated sites
- Discovery — crawl a site or ingest real traffic (HAR/traces) instead of typing endpoints
- Baseline comparison / regression detection across runs
- PDF report export
- Additional tool renderers (JMeter, Gatling) and deeper Locust support
- Persistence of runs, multi-tenancy, auth, CI/CD integration (enterprise hardening)

---

## Design documents

See the `docs/` folder for the architecture, approach, reference-repo teardown, and
tech-stack decisions.