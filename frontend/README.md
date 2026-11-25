# PerfAgent frontend

The React workspace covers project setup, planning, k6 runs, and performance reports. It uses TypeScript, React Router, Vite, and generated FastAPI OpenAPI types. Use Node 22.12 or later.

## Develop locally

Start FastAPI from the repository root:

```bash
uv run uvicorn perfagent.api.app:app --reload --host 127.0.0.1 --port 8080
```

From `frontend/`:

```bash
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies API requests to port **8080**. Set `PERFAGENT_API_URL` before starting Vite if your API uses a different address. The optional checkout sample target runs on port **8000**.

## Demo, build, and test

| Command from `frontend/` | Result |
| --- | --- |
| `npm run demo` | Starts the simulated workspace at <http://127.0.0.1:4174>. Open **Help → Guided tour** to replay the walkthrough. |
| `npm run demo:build` | Writes the static demo to `dist-demo/`. |
| `npm run build` | Type-checks and writes the bundled UI to `../src/perfagent/web/spa/`, served by FastAPI. |
| `npm test` | Runs the Vitest suite. |
| `npm run api:types` | Regenerates TypeScript API types from the local FastAPI app. |

From the repo root, run `node tests/ui_smoke.cjs` for the browser regression suite. It uses fixture APIs and simulated metrics. See the [frontend development reference](../docs/frontend-development.md#production-and-checks) for Chromium configuration and screenshot capture.

## Explore the workspace

- [Screenshot gallery](../docs/screenshots.md) for the guided tour, workflow, dashboard, and reports.
- [Frontend development reference](../docs/frontend-development.md) for source layout, routing, API types, and the compatibility controller.
- [PerfAgent documentation](../README.md) for local setup, architecture, and the roadmap.
