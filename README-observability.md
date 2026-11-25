# PerfAgent — Monitoring, Reporting & Stakeholder Visibility

Adds a Prometheus → Grafana live-monitoring layer, a historical run store,
and role-scoped reporting so every stakeholder can see what's covered,
what's happening in each prod run, and what still needs to complete.

Consistent with **"AI proposes, code proves, humans approve"**: this whole
layer is deterministic code. The only AI-authored column it surfaces is the
existing narrator output — read-only, engineer-scoped.

## How it's built

```
 runner/k6_runner.py ──emits──▶ stats/aggregator.py
        │ (already streams to UI)      │ (RPS, p50/p90/p95/p99, err rate)
        ▼                              ▼
 observability/metrics.py  ◀───feed───┘   ← NEW in-proc Prometheus series
        │
        ▼
   GET /metrics  ──scrape──▶ Prometheus ──▶ Grafana (live + historical)

 analyzer/verdict.py + aggregator summary ──persist──▶ db: run_records
        │                                                   │
 reporting/recorder.py (NEW) ──────────────────────────────┘
        │
 reporting/service.py (role projection) ──serves──▶ api/reporting_routes.py (NEW)
        ├─ GET /reporting/runs      (history, projected per role)
        ├─ GET /reporting/trend     (p95 / error / rps over time)
        └─ GET /reporting/coverage  (declared flows − tested flows)
```

* **Two stores, two questions.** Prometheus/Grafana answers "what's
  happening in this prod run right now" at 5s resolution; the `run_records`
  table answers "how does this run compare over 90 days" and "what's
  covered." Grafana reads both (Prometheus native + a Postgres datasource
  on `run_records`).
* **run_id is deliberately NOT a Prometheus label** — it's high-cardinality
  and would bloat the TSDB. Live series are grouped by
  `(scenario, environment, load_tool)`; per-run detail lives in `run_records`
  and is served by the reporting API. This is the load-bearing decision.
* **Role projection is a whitelist** (`reporting/service.py`), so a new
  sensitive column never leaks by default. Maps onto your `x-access` scheme:
  all new routes are `x-access=read, x-uses-ai=false` — safe to expose
  through the hub gateway at zero token cost.
* **Coverage = declared − tested.** `flow_inventory.py` declares the flows
  expected per environment; `uncovered` is literally the "what needs to
  complete" list; `untracked` flags runs nobody declared.

## New files

| File | What it does |
| :--- | :--- |
| `src/perfagent/observability/__init__.py` | Package export. |
| `src/perfagent/observability/metrics.py` | Prometheus registry, series, `MetricsSink`, `/metrics` renderer. |
| `src/perfagent/observability/hooks.py` | Thin bridge so `k6_runner` feeds the sink without importing Prometheus. |
| `src/perfagent/reporting/__init__.py` | Package export. |
| `src/perfagent/reporting/recorder.py` | Writes a `run_records` row at run completion. |
| `src/perfagent/reporting/flow_inventory.py` | Declared flows per environment (drives coverage). |
| `src/perfagent/reporting/service.py` | Role → allowed-fields projection. |
| `src/perfagent/api/reporting_routes.py` | `/reporting/runs`, `/trend`, `/coverage`. |
| `src/perfagent/db/migrations/versions/0001_add_run_records.py` | Alembic migration for the new table. |
| `tests/test_reporting.py` | Role projection + coverage logic (offline). |
| `tests/test_observability.py` | `MetricsSink` + `/metrics` rendering (offline). |
| `docker-compose.observability.yml` | Prometheus + Grafana stack. |
| `observability/prometheus.yml` | Scrape config (targets `:8080/metrics`). |
| `observability/grafana/provisioning/datasources/datasources.yml` | Prometheus + Postgres datasources. |
| `observability/grafana/provisioning/dashboards/dashboards.yml` | Dashboard provider. |
| `observability/grafana/provisioning/dashboards/perfagent-live-run.json` | Live run dashboard (RPS, error, p95, VUs). |
| `observability/grafana/provisioning/dashboards/perfagent-history.json` | History + coverage dashboard. |

## Modified files (apply by hand — small, exact)

These three need edits to existing files. The snippets are provided as
separate `*_addition.py` files so you can paste them in; nothing in your
current code is removed.

* **`src/perfagent/db/models.py`** — append the contents of
  `src/perfagent/db/models_run_records_addition.py` (the `RunStatus` enum
  and `RunRecord` model). Reuse the existing `Base`; do **not** create a
  second one.
* **`src/perfagent/api/app.py`** — append the contents of
  `src/perfagent/api/app_additions.py` (mount the reporting router + the
  `/metrics` endpoint).
* **`src/perfagent/api/docs.py`** — add the four `ROUTE_METADATA` entries
  shown (commented) at the bottom of `app_additions.py`, so the new routes
  carry `x-access`/`x-uses-ai` like every other route.

Two more wiring edits to do when you're ready to see live data (one line
each, left for you so I don't guess your exact signatures):

* **`src/perfagent/runner/k6_runner.py`** — at run start call
  `sink = observability.hooks.sink_for(ctx)`; on each aggregator snapshot
  call `observability.hooks.on_aggregator_snapshot(sink, snapshot)`; on
  finish `sink.mark_active(False)`.
* **`src/perfagent/analyzer/verdict.py`** (or wherever the run finalizes) —
  call `reporting.recorder.record_run(session, ...)` with the aggregator
  summary and the verdict.

## New dependency

Add `prometheus-client` to `pyproject.toml` / `requirements.txt`:

```
prometheus-client>=0.20
```

## Apply it

```bash
git checkout -b feat/observability

# copy the files into the same paths, then:
uv add prometheus-client            # or edit pyproject + uv sync
uv sync

# create the table (prefer autogenerate so the revision chain links):
uv run alembic revision --autogenerate -m "add run_records"
uv run alembic upgrade head

# offline tests (no k6, no LLM):
uv run pytest -q tests/test_reporting.py tests/test_observability.py
```

## Run it

```bash
# monitoring stack
docker compose -f docker-compose.observability.yml up -d

# agent (exposes /metrics on :8080) + demo target
uv run uvicorn perfagent.api.app:app --reload --port 8080
uv run python -m perfagent.sample_target.app --port 8000

# Grafana: http://localhost:3000  (admin / $GRAFANA_ADMIN_PASSWORD)
# Dashboards auto-provision. Set the Postgres datasource password to match
# your feat/postgres setup for the history dashboard.

# stakeholder views:
curl "http://localhost:8080/reporting/runs?role=executive&environment=prod"
curl "http://localhost:8080/reporting/trend?scenario=checkout&metric=p95_ms"
curl "http://localhost:8080/reporting/coverage?environment=prod"
```

## Push (both remotes, per your workflow)

```bash
git push origin feat/observability
git push company feat/observability
```

## Next

* Grafana alerting on `perfagent_error_rate` and p95 breaches for
  `environment="prod"`.
* Map the four `Role` values to the hub's auth claims when the agent moves
  behind the hub tab; until then the `role` query param demos all views.
* Extend coverage to step/endpoint granularity (not just scenario) once the
  distributed-runner work lands.
