# Frontend migration decision

Recommended next milestone: **React + TypeScript + Vite**, retaining FastAPI as the backend.

PerfAgent is an interactive testing workspace. Its existing Python services already handle planning, generation, execution, Git operations and reports. A client-rendered React application can use those JSON APIs directly; a second server-rendering layer is not needed for the present workflow. This is an application-specific recommendation, not a limitation of Next.js or Angular.

React documents incremental adoption in an existing server-backed application, and Vite documents both React/TypeScript templates and integration with an existing backend:

- [React: add React to an existing project](https://react.dev/learn/add-react-to-an-existing-project)
- [Vite: getting started](https://vite.dev/guide/)
- [Vite: backend integration](https://vite.dev/guide/backend-integration.html)

## Route and component structure

```text
/projects
/projects/new
/projects/:projectId
/projects/:projectId/tests/new
/projects/:projectId/import/script
/projects/:projectId/import/git
/projects/:projectId/tests/:testId
/projects/:projectId/dashboard
/projects/:projectId/runs/:runId
/admin/overview
```

Organize components by project management, test library/editor, workload profiles, run monitor, reports, and integrations. Shared form controls, tables, charts, notices, dialogs, and navigation belong in a small common UI layer.

## Migration sequence

1. Create a `frontend/` React/TypeScript app with Vite. Select compatible dependencies and generate the lockfile when implementation starts.
2. Add routing and a typed API client derived from FastAPI's OpenAPI contract. Keep execution and verdict logic in Python.
3. Move Projects, project settings, dashboards, and the test library first. Preserve the current UI as a fallback during development.
4. Move test creation/review, reusable workload profiles, script imports, and Git framework import.
5. Move run monitoring and reports. Replace global mutable state with project/test/run-specific state; cancel obsolete requests and control polling lifecycle explicitly.
6. Serve a production build from FastAPI, with history fallback for frontend routes and `/api` kept separate. Proxy `/api` during local frontend development.
7. Port the existing browser regression scenarios to the frontend test runner and verify parity before switching the default UI.

For shared deployments, design account authentication and project membership before treating project routes as access boundaries. Administrator authorization belongs on the server, independent of navigation or presentation-role selections.

## Acceptance criteria

- Deep links and refreshes work on project, test and report routes.
- Test names and project identity survive creation, import, runs, reports and Git publication.
- Smoke and full runs retain their distinct execution versions and request counts.
- Switching projects cannot leak stale results from a previous request.
- A report's charts, downloads and baseline use that report's identifiers.
- Users can navigate with a keyboard and use the app on a narrow screen.
- Browser credentials remain in memory; Git and admin tokens are not placed in local storage, route URLs or logs.
- The current project/API/browser regression suite passes before removing the single-file UI.
