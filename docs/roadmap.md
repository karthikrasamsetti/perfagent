# PerfAgent roadmap

[Back to PerfAgent](../README.md)

## Product experience

PerfAgent should open as a standalone product with a public landing page, an interactive sample workspace, and a signed-in workspace for real tests. An agent hub can later link to PerfAgent and pass an approved identity when that integration is permitted.

| Order | Feature | Scope |
| --- | --- | --- |
| 1 | Public landing page | Lead with the performance-testing workflow. Show a real product preview of the dashboard and baseline comparison. Offer **Try demo**, **Sign in**, and **Create account**. Keep the sample demo available without an account. |
| 2 | Sign-in and account creation | Choose an identity provider and signup policy. Build sign-in, signup or invitation acceptance, verification, and sign-out. Keep sessions server-side with secure cookies and enforce project access and roles in the API. Verify session expiry, cross-project isolation, and access to saved reports before opening signup. |
| 3 | Shared UI design | Define typography, color, spacing, and motion across the landing page, account screens, and workspace. Apply the same patterns to navigation, forms, skeletons, charts, errors, and empty states. Verify keyboard use, contrast, responsive layouts, and reduced motion. |
| 4 | Optional agent hub | Add a hub entry and supported single sign-on after provider and permission requirements are agreed. Keep the standalone route available and enforce project access through the same backend checks. |

Use [Aceternity UI](https://ui.aceternity.com/) and [Magic UI](https://magicui.design/) for hero and product-preview composition, [21st.dev](https://21st.dev/) for navigation and form references, and [React Bits](https://reactbits.dev/) and [Motion Primitives](https://github.com/ibelick/motion-primitives) for selective motion. Favor subtle transitions in the workspace and keep the landing page, authentication forms, and essential controls usable with reduced motion.

## Release and execution work

| SNO | Priority | Feature | Remarks |
| --- | --- | --- | --- |
| 1 | Release verification | Manual VoiceOver walkthrough | Check the full workflow and tour on macOS, including keyboard navigation, focus restoration, step and status announcements, chart alternatives, and tables. |
| 2 | Release verification | k6 workflow regression pass | Verify a webpage, an authenticated API, and a multi-step journey. Cover failed authentication, malformed responses, breached thresholds, stop and restart, and report consistency. |
| 3 | Infrastructure dependency | Managed k6 release verification | Use the requested Linux environment to verify the isolated worker and enforced egress end to end. Validate PostgreSQL row-level isolation before enabling managed runs. |
| 4 | After managed k6 | Run reliability and release automation | Finish durable and concurrent run handling, scheduled and CI-triggered runs, and regression alerts. |
| 5 | After managed k6 | Approval-based orchestration | Extend the guided flow from generation through diagnosis and reporting, with a user approval before execution. |
| 6 | Later | Additional protocols | Evaluate k6 coverage for gRPC and WebSocket streaming. |
| 7 | Later | Distributed execution and other engines | Add multiple load generators and evaluate live JMeter and Gatling runners after the managed k6 workflow is verified. |
