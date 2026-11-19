# PerfAgent React workspace

React + TypeScript + Vite frontend for the existing FastAPI application. React Router owns URL navigation and history. The production build is served by FastAPI, so deployment does not require a separate Node server.

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

Open the local URL printed by Vite, normally `http://127.0.0.1:5173`. `/api` and `/legacy` are proxied to PerfAgent on port **8080**. Port **8000** belongs to the optional sample target, not the PerfAgent API. A sample-target response cannot handle `/api/projects`.

Set `PERFAGENT_API_URL` in the repository-root `.env` or shell before starting Vite if the backend uses a different port. For example, in PowerShell: `$env:PERFAGENT_API_URL='http://127.0.0.1:9000'`. Restart Vite after changing the proxy target. Application secrets remain in the backend `.env`; never copy them to `VITE_` variables. Vite reads only the backend-address setting from that file.

## Production and checks

```text
npm run build
npm test
```

The build runs TypeScript checking and writes `src/perfagent/web/spa/`. FastAPI serves that build at `/`, supports browser refreshes on SPA routes, and serves assets under `/assets`. The previous workspace remains at `/legacy`. If no build exists, `/` uses the previous workspace rather than returning a blank page.

Built assets are committed so the Python package/checkouts can serve the UI without installing Node. Rebuild after changing frontend source, and commit the matching output. Do not edit the hashed files directly.

Browser regression checks from the repository root:

```text
node tests/ui_smoke.cjs
```

The harness uses real headless Microsoft Edge with fixture API responses; it does not generate target load. Set `PERFAGENT_EDGE_PATH` for another Edge installation. Set `PERFAGENT_UI_MODE=legacy` to run the shared checks against the preserved workspace.

## Source layout

- `src/pages/`: Projects, test workspace, dashboard, library, monitoring, activity and admin pages.
- `src/components/`: shared navigation, header, dialogs and layout.
- `src/routing/`: route resolution and route tests.
- `src/api/`: shared API error handling, typed requests and generated OpenAPI declarations.
- `src/styles/`: existing visual design and SPA-specific navigation states.
- `src/workspace/controller.js`: explicitly transitional compatibility layer for the existing workflow and advanced editor logic.

Regenerate API declarations after backend contract changes:

```text
npm run api:types
```

This imports the local FastAPI app using the repository `.venv`. `PERFAGENT_PYTHON` can point to a different Python executable. The schema is generated locally without a running backend or copying runtime credentials into the frontend.

## Migration boundary

This first migration replaces the single-file production entry point with editable React page components, stylesheets, a Vite build, TypeScript API types and SPA routing. It preserves behavior rather than redesigning the product.

Workflow state and dynamically generated editor rows still use the compatibility controller. That module exposes a limited-lifetime window bridge for existing generated-row handlers; it is initialized after React mounts and cleaned up on unmount. Pages stay mounted to preserve active form/editor state while routes change. This is not yet a complete conversion to React-managed form and server state.

New frontend features should use React hooks and `src/api/client.ts`. The next refactor is to move project and dashboard state into hooks, followed by the dynamic scenario editor, so the compatibility bridge can be retired. Keep the previous workspace stable as a fallback during that work.

Account authentication and project membership remain backend deployment concerns; the admin overview continues to use its existing server-side token check.
