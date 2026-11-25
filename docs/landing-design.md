# Landing and access design plan

[Back to the roadmap](roadmap.md)

## Landing page

1. **Hero artwork.** The original glass-prism illustration turns a stream of requests into two release traces. Use the violet and indigo palette already used in PerfAgent. Keep the heading and primary action readable on a clean area of the illustration. The artwork is static at every width. Sign-in and Get access reuse a quieter crop.
2. **Product evidence.** The report and dashboard previews sit in the product evidence section just below the hero. Show that the sample run can pass k6 thresholds while a release budget is breached. Keep **Try the demo** as the primary action.
3. **Workflow.** Show one concrete action for each stage. The current links open sample Review, Verify, and Report screens. **How it works** moves to this section and gives it keyboard focus.
4. **Interactive example.** Keep the p95 budget control below the workflow so visitors can test the threshold themselves before opening the workspace.

For product presentation, use clear workflow sections as seen in [Grafana Cloud k6](https://grafana.com/products/cloud/performance-load-testing-k6/), product previews as seen in [Linear](https://linear.app/), and focused evidence illustrations as seen in [Datadog](https://www.datadoghq.com/product/). Create PerfAgent’s own composition and assets.

## Sign-in and account access

- **Get access** opens `/sign-up` with instructions for obtaining a workspace invitation and a link to sign in. The sample demo remains available there.
- **Sign in** opens `/sign-in` and directs invited users to the workspace, where the configured gateway starts organization sign-in.
- **Hosted invitation acceptance** will use the organization identity provider. Verify invitation expiry, wrong-account recovery, MFA, sign-out, and session expiry once the provider is connected.

Use the same artwork palette across the public pages, with a quieter panel around access instructions. Check link navigation, keyboard focus, narrow layouts, and reduced motion before release.
