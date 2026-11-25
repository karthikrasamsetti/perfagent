# Local release verification

[Back to the roadmap](roadmap.md)

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

## Safari with VoiceOver

This manual check remains open. The native Safari control connection failed during verification. The Chromium smoke suite provides automated evidence for keyboard focus, announcements in the accessibility tree, chart data tables, reduced motion, and tour navigation.

For a manual pass, run `npm --prefix frontend run demo` and open <http://127.0.0.1:4174> in Safari. Press **Command + F5** to toggle VoiceOver. Test these points:

- **Guided tour.** Start from the first-visit prompt or Help. Use Next and Previous. Listen for the highlighted control, the step title, and guidance. Confirm Done and Skip return focus to Help.
- **Describe and Review.** Trigger a target-field error, correct it, and draft a plan. Open and close the request preview. Listen for the step changes and validate focus on controls.
- **Verify and Run.** Verify the sample checkout, then start a simulated run. Listen for progress and completion while moving through the page with the keyboard.
- **Report and Dashboard.** Read release readiness and k6 thresholds separately. Open the chart alternatives and inspect table headers and values. Open a saved run from the dashboard.

Record the screen, keys used, and actual announcement for any discrepancy.
