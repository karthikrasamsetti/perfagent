# Project-based performance testing

PerfAgent opens on **Projects**. Create a project or import a Git framework, then keep its tests and execution history together.

## Project setup

Set a project name, description, default target/environment, framework folder, and optional repository, branch and CI templates. Repository credentials are entered for each Git action; they are not project settings.

Existing plans and planning conversations are assigned to **Imported workspace** during the automatic database migration. They keep their script versions and reports. A new database starts with an empty project catalog.

Conversation sessions retain the selected project and test name on the server, including when resuming or building a plan later. The conversation history list is filtered by project.

## Create and reuse tests

1. Open a project and choose **Create test**.
2. Enter the test name and purpose before choosing conversation or manual endpoint planning. Collections can be imported in the manual flow.
3. Review journeys, authentication, data, assertions and thresholds.
4. Save named workload profiles such as Average, Stress and Soak. Selecting a profile applies its load shape and thresholds to the editor; approve/generate to create a new execution version.
5. Validate, preflight, smoke-test, then run the selected workload.
6. Open the project dashboard or test library to review results and select a compatible baseline.

**Import script** and **Git framework** are separate actions within the open project. Existing scripts retain their own name/content. Generated scripts remain the supported path for framework publishing.

Git import can import/synchronize every valid test in a discovered framework. Reimporting a framework/test into the same project updates the existing logical test while retained script snapshots and completed reports stay intact. Tests requiring missing secrets or data still need review before generation. Tests removed from Git are not automatically deleted from PerfAgent.

## Project and admin dashboards

- The project dashboard scopes its summaries, run list, filters and comparison choices to the selected project. Its summary counts cover the project; charts and table statistics cover the current filtered page.
- The admin overview aggregates every project. Set `ADMIN_API_TOKEN` to a long random value in the server environment and restart. Enter that value in **Admin overview**. The browser keeps it in the current page only and sends it as `X-Perfagent-Admin`.
- Empty `ADMIN_API_TOKEN` disables the admin endpoint. The presentation-role dropdown does not grant administrator access.

This remains a local/shared-instance application without user login or project-membership enforcement. Projects organize data; they are not tenant security boundaries. The admin overview has a real token check, but full account authentication, membership and endpoint-level authorization are a separate hosting milestone.

## Git publication

Repository, branch, framework folder and CI selections are inherited from the project. Each test has a distinct folder below `<framework>/tests/<test>/`. Export uses the selected script's frozen model and dataset instead of a newer edited plan. An explicitly supplied export option can override its project default.

Generated framework files continue to use the existing secret extraction and export checks. Tokens are supplied per operation. Project Git settings do not change this source repository's Git branch.

## Next UI milestone

The React SPA now serves the same workflow against FastAPI JSON APIs. See [frontend/README.md](frontend/README.md) for development/build commands and [SPA_MIGRATION.md](SPA_MIGRATION.md) for remaining state refactors. The previous single-file workspace remains at `/legacy` during the transition.
