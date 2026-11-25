# PerfAgent roadmap

[Back to PerfAgent](../README.md)

## Product experience

PerfAgent should open as a standalone product with a public landing page, an interactive sample workspace, and a signed-in workspace for real tests. An agent hub can later link to PerfAgent and pass an approved identity when that integration is permitted.

| Order | Feature | Scope |
| --- | --- | --- |
| 1 | Public landing page | Implemented locally. The landing page at `/` previews a release comparison and links to the sample demo at `/demo` and the project workspace at `/workspace`. The **Sign in** entry explains invite-only access and continues to the protected workspace. |
| 2 | Sign-in and account creation | Start with invite-only accounts and MFA through the existing gateway. Configure the organization identity provider, invitation provisioning, and sign-out. Verify the full hosted login flow before launch. Keep sessions server-side with secure cookies and enforce project access and roles in the API. Verify session expiry, cross-project isolation, and access to saved reports before opening signup. |
| 3 | Shared UI design | Define typography, color, spacing, and motion across the landing page, account screens, and workspace. Apply the same patterns to navigation, forms, skeletons, charts, errors, and empty states. Verify keyboard use, contrast, responsive layouts, and reduced motion. |
| 4 | Optional agent hub | Add a hub entry and supported single sign-on after provider and permission requirements are agreed. Keep the standalone route available and enforce project access through the same backend checks. |

Use [Aceternity UI](https://ui.aceternity.com/) and [Magic UI](https://magicui.design/) for hero and product-preview composition, [21st.dev](https://21st.dev/) for navigation and form references, and [React Bits](https://reactbits.dev/) and [Motion Primitives](https://github.com/ibelick/motion-primitives) for selective motion. Favor subtle transitions in the workspace and keep the landing page, authentication forms, and essential controls usable with reduced motion.

## Current checkpoint

- Git exports preserve timestamps for unchanged tests. A changed script, plan, or committed dataset still produces a Git change.
- Projects and Test Library show inline retry actions on load failure. Test search and empty libraries provide distinct messages.
- Live Run offers a sample data table alongside its chart. Dashboard and Report expose labeled regions for their chart tables.
- Hosted sign-in still requires the organization's gateway and identity provider configuration to verify invitations, session expiry, and sign-out.

## Release and execution work

| SNO | Priority | Feature | Remarks |
| --- | --- | --- | --- |
| 1 | Deferred | Manual VoiceOver walkthrough | Check the full workflow and tour on macOS, including keyboard navigation, focus restoration, step and status announcements, chart alternatives, and tables. |
| 2 | Verified locally | k6 workflow regression pass | Real k6 covers a webpage, an authenticated API, a multi-step journey, failed auth, malformed JSON, a threshold breach, stop/restart, and saved reports. The [release checklist](release-verification.md) records the reproducible checks. |
| 3 | Infrastructure dependency | Managed k6 release verification | Use the requested Linux environment to verify the isolated worker and enforced egress end to end. Validate PostgreSQL row-level isolation before enabling managed runs. |
| 4 | After managed k6 | Run reliability and release automation | Finish durable and concurrent run handling, scheduled and CI-triggered runs, and regression alerts. |
| 5 | After managed k6 | Approval-based orchestration | Extend the guided flow from generation through diagnosis and reporting, with a user approval before execution. |
| 6 | Later | Additional protocols | Evaluate k6 coverage for gRPC and WebSocket streaming. |
| 7 | Later | Distributed execution and other engines | Add multiple load generators and evaluate live JMeter and Gatling runners after the managed k6 workflow is verified. |
