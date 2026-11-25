# Operations and API reference

[Back to PerfAgent](../README.md)

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

## Safety notes

> [!WARNING]
> **Only run load against systems you own or have explicit written permission to test.**
> Generating load against systems you don't control can cause outages and may be illegal.

- The human approval gate sits **before** any load is fired — always review the plan first.
- Start with low user counts and short durations on any new target, then scale up.
- Sensitive data is redacted before it reaches the LLM; extend detectors in
  `guardrails/redaction.py` for your environment before pointing at production-adjacent data.
- **Skip TLS verification** is for test/dev hosts only — never enable it against production.
