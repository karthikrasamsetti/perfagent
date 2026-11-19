# PerfAgent UI and product review

Reviewed November 19, 2026.

## Implementation update

React migration: the default built UI is now a React/TypeScript/Vite SPA with seven page components, shared navigation/dialogs, OpenAPI-generated request types, browser history and deep-link refresh support. FastAPI serves the committed production assets. The previous workspace remains at `/legacy`. Workflow state and dynamic editor rows are retained in an extracted compatibility controller; see [frontend/README.md](frontend/README.md) for the exact boundary and run/build commands.

Migration validation includes 50 backend workflow/API checks, 7 frontend unit tests, 42 React browser checks, and 34 checks against the previous workspace. Browser checks use fixture APIs; the backend smoke regression uses a temporary local HTTP target.

Project milestone: the app now starts with Projects, captures a test name before planning, offers separate script/Git import actions, retains reusable workload profiles, and provides project-scoped dashboards/libraries. An admin-token-protected endpoint supplies the all-project overview. Legacy data is migrated into Imported workspace. See [PROJECT_WORKFLOW.md](PROJECT_WORKFLOW.md) for usage and the precise access-control scope; see [SPA_MIGRATION.md](SPA_MIGRATION.md) for the next React/TypeScript/Vite milestone.

Project validation: the complete regression run finished with **415 passed, 25 skipped**. The final conversation/project/migration/API checks passed **57 tests, with 3 skipped**. The updated Edge harness exercises project creation, naming before planning, separate imports, reusable workloads, admin rejection/success, scoped dashboards, reports, and desktop/mobile navigation.

Latest tester-workflow update:

- Smoke request totals are visible in every dashboard role, including the default Executive view. The prior role projection omitted the Requests column.
- Smoke scripts start one user per journey immediately instead of ramping from zero.
- Plans support a test name and a custom script filename. These, plus HTTP method/path summaries and smoke/full mode, are frozen into run identity and shown in Dashboard, comparison choices, History, and report context. Uploaded scripts have named identity too; their placeholder plan is not presented as a measured endpoint list.
- The dashboard can filter by a saved test independently of target, so checkout and browsing runs against the same host can be isolated.
- Verification: 32 focused tests passed, including an actual 10-second k6 run against a temporary local HTTP server. Its nonzero request count agreed across live metrics, the saved report, and the Executive dashboard. A subsequent upload/data compatibility run passed 27 tests (two real-engine tests deselected because the local smoke check had already run). All 24 fixture-backed Edge browser checks passed.

For the next tester-focused milestone, prioritize endpoint-specific SLOs, a clear authentication/correlation diagnostic, and release-gate summaries. Keep scenario identity separate from workload shape so the same journey can be reused for smoke, average-load, stress and soak tests; see [k6 automation guidance](https://grafana.com/docs/k6/latest/testing-guides/automated-performance-testing/).

The report-reliability fixes and local-workflow improvements below are now implemented:

- Downloads use the displayed report's identity and persisted metrics, including after the live-run registry is cleared.
- Reports use the original run ID as the database primary key; repeated reads reuse the saved payload.
- Reports retain their own time-series samples, plan identity, status, workload metadata, and selected baseline. Missing older measurements display as unavailable.
- Script versions freeze the load model and exact dataset contents in a new `script_snapshots` table. The Alembic migration runs through normal application startup. Existing scripts freeze their available inputs on the next run; their historical inputs cannot be reconstructed retroactively.
- Dashboard target/date/verdict filters run on the server, with pagination. Viewer target filtering is disabled and unavailable chart values are excluded.
- Readiness checks inspect frozen inputs without traffic. Pre-flight checks use frozen inputs and send endpoint requests. Validation uses `k6 inspect` without traffic. Smoke runs create a separate 10-second k6 script with one peak user per journey and no graceful-stop extension.
- k6 iteration-rate mode preserves the requested total rate and preallocated-user budget across journeys. Both settings must be at least the journey count. Achieved iterations and dropped iterations are reported separately from HTTP requests/second.
- Named environment presets retain target URLs and labels locally in the browser. Release/commit labels and workload/data hashes are retained with reports. Baselines can be selected or cleared; incompatible workloads and partial runs cannot be selected as baselines.
- Core run, report, history, and activity failures are surfaced in the UI. Run-start requests are guarded against duplicate clicks.

The sections below preserve the original review findings for context. Shared-account authorization, organization-wide environment management, and live third-party integration validation remain separate work; the role dropdown is still a presentation control.

Implementation validation: the broad suite completed with **402 passed, 25 skipped**. Subsequent targeted checks passed **54 tests** for baseline, preflight, verdicts, and migrations, followed by **39 tests** for the final renderer and API changes. All **22 browser checks** passed with no uncaught JavaScript errors. Browser checks use real Edge with fixture APIs, so they do not establish live AI, k6, Git, or Jenkins connectivity.

## Verification

Real headless Microsoft Edge, desktop 1440 × 1000 and mobile 390 × 844, using the actual HTML/JavaScript with fixture API responses. No performance load was generated by this browser check.

13 of 14 browser checks passed. Passed: initial Create view, collapsed toggle visibility, sidebar persistence after reload, recent-run report buttons, comparison rendering, target filtering, report opening, History/Monitoring/Activity navigation, mobile navigation opening/closing, and mobile viewport fit. No uncaught JavaScript exceptions were observed. Failed: saved report download context.

These checks do not establish that every form works against the real backend. Live AI planning, actual k6 execution, Git credentials, Jenkins, external monitoring embeds, and Postgres require separate configured integration checks.

The earlier focused reporting/API run passed all 12 tests. A full-suite run during this review reached beyond 51% with no failures printed, then continued slowly with skipped tests. It was interrupted without a final summary; the full suite is not verified as passing.

## Fix first

| Priority | Finding | Consequence | Recommended change |
| --- | --- | --- | --- |
| P1 | Opening a saved report does not update `currentRunId`; Download report uses that variable. Browser confirmed. | Download does nothing in a fresh session or can refer to a previously active run. | Give the displayed report its own saved-result ID and download from that context. |
| P1 | Report download only looks in the in-memory run registry. Source inspection. | Download fails after restarting the server, despite the saved report remaining visible. | Render downloads from persisted report data; test after restarting and with an empty run registry. |
| P1 | Every successful live-report GET inserts another result row; there is no stable original-run uniqueness check. Source inspection. | Repeated requests can duplicate history and change the baseline used for comparison. | Persist one result per original run, enforce uniqueness, and make repeated report reads return the saved result. |
| P1 | Saved reports draw time-series from global `chartData` and load plan trends using global `currentPlanId`. Opening a report sets neither to that report. Source inspection. | Charts can be empty or belong to a previously viewed/run test. | Store run samples and plan identity with the report; use report-local state. Show unavailable when samples were not retained. |
| P2 | The original script is retained for reruns, but execution loads the current plan and the most recent data upload matching a filename. Source inspection. | Same script does not guarantee the same thresholds or test data on rerun. | Version the plan, script, environment configuration, and data-file identity together. Distinguish replay from running with updated inputs. |
| P2 | Several fetch/render/stop failures are swallowed by empty catch blocks. Source inspection. | A stopped spinner, stale data, or unresponsive action can look like success. | Show loading/error/retry states; check HTTP status; keep stale data visibly marked. |
| P2 | Dashboard filtering uses only the latest 100 results. Viewer rows omit targets and error rates. Source inspection. | Target filtering can remove all viewer results; missing errors can be presented as zero by charts. | Implement server-side filters and pagination; disable unavailable filters and show missing metrics as unavailable. |

The “View as” dropdown controls field presentation. It should not be treated as account authorization. Before shared hosting, derive permissions from authenticated server-side identity and enforce them on report access and execution endpoints.

## Product improvements, in order

1. **Reliable results:** finish the P1 fixes, make reports immutable, distinguish stopped/failed/inconclusive runs, and prove persistence across restart.
2. **A guided first successful test:** add a preflight checklist for target reachability, authentication, data availability, engine availability, and estimated users/duration. Offer a small smoke run before a larger run.
3. **Actionable reports:** show slow endpoints, failed assertions, sample counts, achieved throughput, load shape, environment, and threshold reasons. Compare equivalent workloads and identify the selected baseline explicitly.
4. **Traffic modeling:** retain the existing ramp/spike/soak/stress options, then add a target iteration-rate mode, achieved-versus-requested traffic, and dropped-iteration visibility. Iterations per second are not necessarily requests per second when a journey sends multiple requests.
5. **Repeatable team workflow:** named environments, reusable authenticated journeys, versioned datasets, release/commit labels, saved baseline selection, and CI threshold gates using the existing Git/Jenkins integrations.

## Acceptance checklist before a release

- Create/import a plan, review it, generate a script, validate it, preflight it, and run against an explicitly selected local fixture target.
- Assert successful, failed-threshold, failed-authentication, no-data, stopped, and engine-error outcomes.
- Reopen each report from Dashboard and History; verify metrics, selected baseline, logs, downloads, and rerun inputs.
- Restart the application and repeat report viewing/download checks.
- Verify repeated report fetches do not create extra history rows.
- Exercise dashboard filters, roles, unavailable metrics, empty results, server failures, and older reports.
- Check mobile layouts, keyboard-only navigation, focus visibility, and sidebar expand/collapse.
- Validate configured Git/Jenkins flows separately, including denied credentials and unavailable services.

## Reference documentation

- [k6 thresholds](https://grafana.com/docs/k6/latest/using-k6/thresholds/): metric-based pass/fail criteria and automation.
- [k6 constant arrival rate](https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/constant-arrival-rate/): fixed iteration rate independent of response time.
- [k6 built-in metrics](https://grafana.com/docs/k6/latest/using-k6/metrics/reference/): dropped iterations and execution metrics.
