# Frontend development reference

[Back to PerfAgent](../README.md)

## Technology stack

| Layer | Stack |
|---|---|
| UI and routing | React 19, React DOM, React Router 7, CSS, and Canvas |
| Type checking and build | TypeScript 5.9, Vite 8, Node 22.12+ |
| API integration | Fetch, FastAPI OpenAPI schema, and generated types via openapi-typescript |
| Testing | Vitest for frontend tests and headless Chromium for workflow smoke tests |

## How the UI fits together

- **Projects and Project Workspace** organize saved tests, the configured Git framework, and saved runs.
- **Describe → Review Plan → Verify → Run → Report** takes a test from input to saved evidence. Describe accepts an optional JSON-field existence check per endpoint. Review exposes per-request assertions and dynamic data sources.
- **Script history** shows the latest and previous versions with preview and download actions. Repeated approval reuses an identical latest version.
- **Dashboard** shows workload trends, run outcomes, and compatible baseline regressions. Use the history filters and the chart run selector to open a saved report.
- **Release readiness** appears in saved reports and for the latest matching dashboard run with a configured policy. Open a passing full run to approve the baseline and set budgets for its test environment. Use the comparison charts and endpoint table to review a candidate.
- **Traffic planning** in Describe reads aggregate CSVs locally. Apply the busiest observed window or average rate and check the resulting journey rate in Review. [Traffic planning screen](screenshots/traffic-planning.png)
- **Release screens** with sample data. [Dashboard](screenshots/release-dashboard.png), [Run report](screenshots/release-report.png), [Comparison](screenshots/release-comparison.png), [Mobile dashboard](screenshots/release-dashboard-mobile.png), [Mobile report](screenshots/release-report-mobile.png).
- **Describe and Review** show the request order before load settings, then show where each dynamic value comes from and which request field uses it. [Describe](screenshots/describe-redesign.png), [Review](screenshots/review-plan-redesign.png), [Mobile Review](screenshots/review-plan-redesign-mobile.png).
- **Verify** separates readiness and syntax checks from target verification, smoke, and full load. **Live Run** shows workload context, throughput, latency, errors, and endpoint results. [Verify](screenshots/verify-redesign.png), [Live Run](screenshots/live-run-redesign.png).
- **Workspace screens**. [Projects](screenshots/projects-redesign.png), [Test Library](screenshots/test-library-redesign.png), [Activity](screenshots/activity-redesign.png), [Monitoring](screenshots/monitoring-redesign.png). Monitoring saves links in this browser and loads a sandboxed embed when you select **Preview**. Use **Open in new tab** for dashboards that require direct sign-in.
- **Typography** uses self-hosted Geist and IBM Plex Mono. Font licenses ship with the frontend build.
- **Run Report** shows the backend verdict and narrative, linked evidence, the synchronized timeline, endpoint rankings, and export actions.

The workspace account menu shows Local, Demo, or Managed access and groups AI usage with the session context.

The browser sends planning and reporting requests to FastAPI. The backend owns the guarded AI provider, execution credentials, script generation, verification, and metrics. See the [system architecture](architecture.md) and [AI roles](architecture.md#ai-roles).

## Development

Use Node 22.12 or newer. From `frontend/`:

```text
npm ci
npm run dev
```

Start the Python backend separately from the repository root:

```text
uv run uvicorn perfagent.api.app:app --reload --port 8080
```

Open the local URL printed by Vite, normally `http://127.0.0.1:5173`. The workspace is at `/workspace`. `/api` and `/legacy` are proxied to PerfAgent on port **8080**. Port **8000** belongs to the optional sample target, not the PerfAgent API. A sample-target response cannot handle `/api/projects`.

From the repository root, the equivalent frontend command is `npm --prefix frontend run dev`. Follow the [first UI test](local-setup.md#first-ui-test) to verify the workflow locally.

Set `PERFAGENT_API_URL` in the repository-root `.env` or shell before starting Vite if the backend uses a different port. For example, in PowerShell: `$env:PERFAGENT_API_URL='http://127.0.0.1:9000'`. Restart Vite after changing the proxy target. Application secrets remain in the backend `.env`; never copy them to `VITE_` variables. Vite reads only the backend-address setting from that file.

## Production and checks

```text
npm run build
npm test
```

The build runs TypeScript checking and writes `src/perfagent/web/spa/`. FastAPI serves the landing page at `/` and the workspace at `/workspace`, supports browser refreshes on SPA routes, and serves assets under `/assets`. The previous workspace remains at `/legacy`. If no build exists, `/` uses the previous workspace rather than returning a blank page.

Built assets are committed so the Python package/checkouts can serve the UI without installing Node. Rebuild after changing frontend source, and commit the matching output. Do not edit the hashed files directly.

Browser regression checks from the repository root:

```text
node tests/ui_smoke.cjs
```

The harness uses real headless Microsoft Edge with fixture API responses; it does not generate target load. Set `PERFAGENT_EDGE_PATH` to the executable path for Edge or Chrome. Set `PERFAGENT_SCREENSHOT_DIR` to capture named screenshots from the fixture walkthrough. Set `PERFAGENT_UI_MODE=legacy` to run the shared checks against the preserved workspace.

The React checks cover keyboard navigation between workflow stages, focus handoff, the browser accessibility tree, workflow text contrast, reduced motion, and narrow-screen layouts. In the Describe mode tabs, use the arrow keys to switch between available modes.

## Source layout

- `src/pages/`: Projects, test workspace, dashboard, library, monitoring, activity and admin pages.
- `src/components/`: shared navigation, header, dialogs and layout.
- `src/routing/`: route resolution and route tests.
- `src/api/`: shared API error handling, typed requests and generated OpenAPI declarations.
- `src/styles/`: shared workspace styles, SPA layout, and responsive results and review views.
- `src/workspace/controller.js`: explicitly transitional compatibility layer for the existing workflow and advanced editor logic.

Regenerate API declarations after backend contract changes:

```text
npm run api:types
```

This imports the local FastAPI app using the repository `.venv`. `PERFAGENT_PYTHON` can point to a different Python executable. The schema is generated locally without a running backend or copying runtime credentials into the frontend.

## Workspace implementation

React owns the production page layouts and routing. The previous single-file workspace remains available at `/legacy`.

Workflow state and dynamically generated editor rows still use the compatibility controller. That module exposes a limited-lifetime window bridge for existing generated-row handlers; it is initialized after React mounts and cleaned up on unmount. Pages stay mounted to preserve active form/editor state while routes change. This is not yet a complete conversion to React-managed form and server state.

New frontend features should use React hooks and `src/api/client.ts`. The next refactor is to move project and dashboard state into hooks, followed by the dynamic scenario editor, so the compatibility bridge can be retired. Keep the previous workspace stable as a fallback during that work.

Account authentication and project membership remain backend deployment concerns; the admin overview continues to use its existing server-side token check.
