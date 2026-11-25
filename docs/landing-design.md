# Landing and access design plan

[Back to the roadmap](roadmap.md)

## Landing page

1. **Hero artwork.** The original glass-prism illustration turns a stream of requests into two release traces. Use the violet and indigo palette already used in PerfAgent. Keep the heading and primary action readable on a clean area of the illustration. The hero artwork follows scroll position on desktop and uses a smaller shift on mobile. Reduced-motion preferences keep the composition static. The same prism-shaped mark appears in public navigation, the workspace, and the browser tab. Sign-in and Get access reuse a quieter crop.
2. **Product evidence.** The report and dashboard previews sit in the product evidence section just below the hero, against a soft crop of the prism artwork. The preview settles into place as it enters the viewport. Show that the sample run can pass k6 thresholds while a release budget is breached. Keep **Try the demo** as the primary action.
3. **Workflow.** Show one concrete action for each stage. Each entire card opens its sample Review, Verify, or Report screen. Cards visibly respond to hover, keyboard focus, and touch. **How it works** moves to this section and gives it keyboard focus.
4. **Interactive example.** Keep the p95 budget control below the workflow so visitors can test the threshold themselves before opening the workspace.

For product presentation, use clear workflow sections as seen in [Grafana Cloud k6](https://grafana.com/products/cloud/performance-load-testing-k6/), product previews as seen in [Linear](https://linear.app/), and focused evidence illustrations as seen in [Datadog](https://www.datadoghq.com/product/). Create PerfAgent’s own composition and assets.

## Sign-in and account access

- **Get access** opens `/sign-up` with instructions for obtaining a workspace invitation and a link to sign in. The sample demo remains available there.
- **Sign in** opens `/sign-in` and directs invited users to the workspace, where the configured gateway starts organization sign-in.
- Landing, Sign in, and Get access use in-app navigation. Continue to workspace uses in-app navigation in local mode and a full browser handoff in managed mode so the gateway can start sign-in. The demo opens its own isolated document.
- **Hosted invitation acceptance** will use the organization identity provider. Verify invitation expiry, wrong-account recovery, MFA, sign-out, and session expiry once the provider is connected.

Use the same artwork palette across the public pages, with a quieter panel around access instructions. Check link navigation, keyboard focus, narrow layouts, and reduced motion before release.
