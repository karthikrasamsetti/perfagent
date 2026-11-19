# Frontend migration decision

Implemented first migration: **React + TypeScript + Vite**, retaining FastAPI as the backend. See [frontend/README.md](frontend/README.md) for development, builds and the compatibility boundary.

The production entry point now renders seven React page components and shared navigation/dialogs, uses React Router for navigation and deep-link refreshes, and has TypeScript request declarations generated from OpenAPI. FastAPI serves the built assets and retains `/legacy` as a fallback. The advanced editor and existing workflow state remain in an extracted compatibility controller; converting that state to React hooks is the next incremental refactor.

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

## Follow-up migration sequence

1. Move Projects, project settings, dashboards and library state from the compatibility controller into React hooks and the typed API client.
2. Replace generated scenario/request-data rows with React components and controlled forms.
3. Move run polling and report state into project/test/run-specific hooks with explicit cancellation and cleanup.
4. Retire window compatibility bindings as each feature's dynamic rows and state are converted.
5. Keep API, component, route and real-browser regression checks passing before removing `/legacy`.

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
