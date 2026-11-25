# Repository map

[Back to PerfAgent](../README.md) · [Feature tracker](feature-tracker.md)

| Area | What belongs there |
| --- | --- |
| [frontend](../frontend) | React pages, shared components, browser routes, typed API client, stylesheet, and simulated demo backend. |
| [API](../src/perfagent/api) | FastAPI routes and OpenAPI docs, workspace and project access, run checkpointing, release policies, and integrations. |
| [Planner](../src/perfagent/planner), [chat](../src/perfagent/chat), and [providers](../src/perfagent/providers) | Workload drafting, conversational state, and server-side AI provider adapters. |
| [Contracts](../src/perfagent/contracts), [importers](../src/perfagent/importers), and [data](../src/perfagent/data) | Workload schemas, API imports, datasets, and input processing. |
| [Generator](../src/perfagent/generator), [guardrails](../src/perfagent/guardrails), and [runner](../src/perfagent/runner) | Script rendering, redaction, k6 execution, and the isolated worker groundwork. |
| [Analyzer](../src/perfagent/analyzer) and [reporting](../src/perfagent/reporting) | Computed verdicts, release budgets, reporting summaries, and historical metrics. |
| [Database](../src/perfagent/db) | SQLAlchemy models and Alembic migrations for SQLite and PostgreSQL. |
| [Packaged web assets](../src/perfagent/web) | Built React workspace served by FastAPI and the legacy UI. Rebuild the SPA from the frontend source. |
| [Git export](../src/perfagent/gitexport) and [CI templates](../src/perfagent/ci) | Exported test frameworks and integration templates. |
| [Tests](../tests) and [release workflow](../.github/workflows/release-checks.yml) | Backend tests, browser smoke checks, and standalone GitHub Actions jobs. |
| [Deployment](../deploy) and [observability](../observability) | Managed worker build and optional Prometheus/Grafana provisioning. |
| [Examples](../examples) and [sample target](../src/perfagent/sample_target) | Sample workloads and a local HTTP target. |
| [Screenshots](screenshots.md) and [patch archive](archive/patches/README.md) | Documentation captures and historical development patches. |

Local credentials, databases, logs, dependencies, and temporary build caches are ignored by Git. The packaged production SPA is tracked because FastAPI can serve it directly.
