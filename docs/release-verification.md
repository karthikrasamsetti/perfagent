# Local release verification

[Back to the roadmap](roadmap.md)

## Continuous integration

The [standalone release workflow](../.github/workflows/release-checks.yml) runs on pull requests, pushes to the default branches, and manual dispatch. The backend job provisions the checksum-verified k6 binary before pytest so the localhost walkthrough can execute. The frontend job runs Vitest, builds the workspace, and exercises it in Chrome with fixture APIs.

The jobs use temporary test data. Hosted sign-in, managed workers, and Safari VoiceOver have separate verification.

## Gate an existing release report

On a saved report, choose **Download JSON**. Use that file with the gate. To fetch a fresh report in CI from a local PerfAgent instance, substitute the saved candidate ID:

```bash
curl --fail --silent --show-error \
  http://127.0.0.1:8080/api/runs/REPLACE_WITH_SAVED_RUN_ID/saved-report \
  --output candidate-report.json
uv run python -m perfagent.ci.release_gate candidate-report.json \
  --environment staging --release v2.4
```

Use the exit code in your CI job:

| Code | Outcome |
| --- | --- |
| 0 | An exact environment and release match was found, the full run finished, k6 passed, and release readiness is ready. |
| 1 | The matching full run has a blocked release decision. |
| 2 | The saved report is absent, invalid, mismatched, incomplete, or lacks sufficient release evidence. |

The gate evaluates the report file without sending traffic. Fetch a fresh report from the trusted workspace service in CI so it reflects the applicable release policy.

## Real k6

Run from the repository root with an installed k6 binary:

```bash
uv run pytest -q tests/test_run_reliability.py -k local_k6_release_walkthrough
```

The walkthrough uses real k6 with a loopback HTTP fixture, an isolated SQLite database, and no AI provider. It generates and verifies each script, checks the run verdict, and compares the saved report and HTML export.

| Scenario | Expected evidence |
| --- | --- |
| Webpage | HTML content check passes and the full run passes. |
| Authenticated API | A bearer-authenticated JSON request verifies and the full run passes. |
| Failed authentication | Verification reports HTTP 401. The real run breaches the error threshold. |
| Multi-step journey | Capture an order ID from a POST and use it in a following GET. Malformed JSON fails verification. Restoring the JSON response yields a passing run. |
| Stop and restart | Stop a running workload. Its report is inconclusive. Run the same script under a new release label and verify it finishes and passes. |

## Interrupted-run recovery

The runner saves a launch record and periodically checkpoints measurements. If the backend loses its in-memory owner, the bookmark can reopen a partial report once the 30-second lease expires. The recovery test simulates process loss, checks that the saved measurements and logs survive, and verifies that no load starts.

```bash
uv run pytest -q tests/test_run_reliability.py -k expired_checkpoint
```

## Safari with VoiceOver

This manual check remains open. The native Safari control connection failed during verification. The Chromium smoke suite provides automated evidence for keyboard focus, announcements in the accessibility tree, chart data tables, reduced motion, and tour navigation.

For a manual pass, run `npm --prefix frontend run demo` and open <http://127.0.0.1:4174> in Safari. Press **Command + F5** to toggle VoiceOver. Test these points:

- **Guided tour.** Start from the first-visit prompt or Help. Use Next and Previous. Listen for the highlighted control, the step title, and guidance. Confirm Done and Skip return focus to Help.
- **Describe and Review.** Trigger a target-field error, correct it, and draft a plan. Open and close the request preview. Listen for the step changes and validate focus on controls.
- **Verify and Run.** Verify the sample checkout, then start a simulated run. Listen for progress and completion while moving through the page with the keyboard.
- **Report and Dashboard.** Read release readiness and k6 thresholds separately. Open the chart alternatives and inspect table headers and values. Open a saved run from the dashboard.

Record the screen, keys used, and actual announcement for any discrepancy.
