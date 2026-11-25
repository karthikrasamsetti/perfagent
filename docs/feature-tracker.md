# PerfAgent feature tracker

[Back to PerfAgent](../README.md) · [Roadmap](roadmap.md) · [Repository map](repository-map.md)

**Local** means available in the standalone local workspace. **Verified locally** adds a passing automated or real-k6 check. Hosted and planned features have their own acceptance criteria.

| SNO | Feature | Status and remarks | Guide |
| --- | --- | --- | --- |
| 1 | Landing page, sign-in, and invitation entry | Local. Visitors can open the demo and see release-budget examples. Hosted authentication uses the organization's gateway. | [Local setup](local-setup.md) |
| 2 | Interactive demo | Verified locally. Sample checkout, verification, run, and report use in-browser data. | [Workflow](workflow.md) |
| 3 | Guided tour | Verified in Chrome on desktop and mobile. Tour steps navigate and move focus to real controls. Manual Safari VoiceOver is deferred. | [Release verification](release-verification.md#safari-with-voiceover) |
| 4 | Projects and Test Library | Local. Search tests, resume drafts and scripts, open the latest report, and inspect the Git framework. | [Project workspace](../PROJECT_WORKFLOW.md) |
| 5 | AI-assisted planning | Local. Draft from explicit endpoints or supported imports and review the result before generating a script. | [Workflow](workflow.md) |
| 6 | Conversational planning | Local when a provider is configured. Answers refine a saved draft before review. | [Conversation mode](workflow.md#conversation-mode) |
| 7 | Workload design | Local. VU and arrival-rate executors, fixed iterations, traffic profiles, and aggregate traffic import. | [Workflow](workflow.md) |
| 8 | Dynamic test data and correlation | Local. Use uploaded data, generated values, and values captured from earlier responses. | [Dynamic test data](workflow.md#dynamic-test-data--the-three-sources) |
| 9 | Response assertions | Verified locally. Status, body, JSON field, and timing checks. The release walkthrough covers malformed JSON and failed authentication. | [Release verification](release-verification.md#real-k6) |
| 10 | Script generation and version history | Local. Generate k6, Locust, JMeter, or Gatling scripts. Live execution is integrated for k6. | [Architecture](architecture.md) |
| 11 | Verify and execution preview | Local. Check syntax, see the saved workload, verify requests, and explicitly start load. | [Workflow](workflow.md) |
| 12 | Local k6 execution | Verified locally. The real-k6 fixture covers webpage, authenticated API, multi-step journey, threshold failures, stop, and restart. | [Release verification](release-verification.md#real-k6) |
| 13 | Live monitoring and run recovery | Local. Live samples, logs, stop control, run links, automatic terminal reports, and interruption recovery from the last checkpoint through a bookmark or Test Library. | [Workflow](workflow.md) |
| 14 | Reports and HTML exports | Verified locally. Deterministic verdicts, saved evidence, request and journey results, timing phases, and HTML and JSON downloads. | [Workflow](workflow.md) |
| 15 | Dashboard and release readiness | Verified locally. Compare an approved baseline and candidate, track historical metrics, and identify the largest measured endpoint p95 increase. | [Screenshot gallery](screenshots.md) |
| 16 | Git import and export | Verified locally. Unchanged exports create no commit. Changed test inputs create a new commit. | [Integrations](integrations.md) |
| 17 | Jenkins integration | Local integration available. A real Jenkins instance needs its own approved configuration. | [Integrations](integrations.md) |
| 18 | Standalone CI verification | Workflow is in the repo. The first GitHub Actions run is pending publication and a PR or eligible push. | [Release verification](release-verification.md#continuous-integration) |
| 19 | Observability and audit | Local. Logs, audit, AI usage, and a Prometheus/Grafana setup. | [Observability](../README-observability.md) |
| 20 | Managed access and project roles | Server-side rules are tested locally. Real invitations, MFA, sign-out, and session expiry need the organization gateway. | [Architecture](architecture.md) |
| 21 | Managed k6 execution | Pending Linux and PostgreSQL staging verification. Managed execution remains disabled. | [Architecture](architecture.md) |
| 22 | Scheduled load and regression notifications | Planned. Configure a runner, target and workload limits, and approved notification destinations before enabling scheduled load or delivery. | [Roadmap](roadmap.md) |
| 23 | API and browser security | Local safeguards include redacted AI inputs, browser write protection, project authorization, upload validation, and bounded execution. Hosted isolation still needs its own verification. | [Architecture](architecture.md) |
| 24 | Saved-report CI gate | Verified locally. A CI job can check a saved JSON report for ready, blocked, or insufficient evidence and match its environment and release. | [Release verification](release-verification.md#gate-an-existing-release-report) |
| 25 | Hub, distributed runners, and additional protocols | Later. Hub integration needs permission. Distributed execution and additional live engines follow managed k6 verification. | [Roadmap](roadmap.md) |
