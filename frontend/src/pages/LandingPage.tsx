import { useState } from 'react'
import { Icon } from '../components/Icon'
import report from '../../../docs/screenshots/release-comparison.png'
import dashboard from '../../../docs/screenshots/release-dashboard.png'
import './landing.css'

export function LandingPage({ access = false }: { access?: boolean }) {
  const [showDashboard, setShowDashboard] = useState(false)
  return (
    <div className="public-site">
      <a className="skip-link" href="#product">Skip to content</a>
      <header className="public-nav public-width">
        <a href="/" className="public-brand"><span className="sb-logo" aria-hidden="true"><i /><i /><i /></span>PerfAgent</a>
        <nav aria-label="Main navigation">
          <a className="public-nav-workflow" href="/#workflow">How it works</a>
          <a href={access ? "/demo" : "/sign-in"}>{access ? "Try demo" : "Sign in"} <span aria-hidden="true">↗</span></a>
        </nav>
      </header>
      {access ? <main id="product" tabIndex={-1} className="public-access public-width">
        <section aria-labelledby="access-title">
          <span className="public-access-icon"><Icon name="shield" /></span>
          <h1 id="access-title">Sign in to PerfAgent</h1>
          <p>Hosted workspaces are invite-only. Use the organization account from your invitation and complete multi-factor sign-in when prompted.</p>
          <div className="public-actions">
            <a className="public-primary" href="/workspace">Continue to workspace <span aria-hidden="true">↗</span></a>
            <a className="public-secondary" href="/demo">Try the demo</a>
          </div>
          <p className="public-access-note">Need an invitation? Ask your workspace administrator for access.</p>
        </section>
      </main> : <main id="product" tabIndex={-1}>
        <section className="public-hero public-width" aria-labelledby="public-title">
          <div className="public-intro">
            <h1 id="public-title">Know how your app performs <em>under load.</em></h1>
            <p>Turn an endpoint or API spec into a k6 test. Verify what it sends, watch it run, and see what changed between releases.</p>
            <div className="public-actions">
              <a className="public-primary" href="/demo">Try the demo <span aria-hidden="true">↗</span></a>
              <a className="public-secondary" href="#workflow">Explore the workflow <span aria-hidden="true">↓</span></a>
            </div>
          </div>
          <figure className="public-report">
            <div className="public-report-bar">
              <div className="public-preview-switch" role="group" aria-label="Product preview">
                <button type="button" aria-pressed={!showDashboard} onClick={() => setShowDashboard(false)}>Release report</button>
                <button type="button" aria-pressed={showDashboard} onClick={() => setShowDashboard(true)}>Dashboard</button>
              </div>
              <strong>Sample data</strong>
            </div>
            <img id="public-preview" src={showDashboard ? dashboard : report} alt={showDashboard
              ? 'PerfAgent dashboard with historical performance and release readiness.'
              : 'PerfAgent release report comparing a sample candidate with its approved baseline.'} />
            <figcaption>{showDashboard
              ? 'Track latency and results across saved runs.'
              : 'Compare a candidate against an approved baseline.'}</figcaption>
          </figure>
        </section>
        <section className="public-workflow public-width" id="workflow" aria-labelledby="public-workflow-title">
          <h2 id="public-workflow-title">From a target to a release decision</h2>
          <div className="public-steps">
            <article><Icon name="workspace" /><h3>Plan the workload</h3><p>Describe requests, set a traffic goal, and review the draft. Add response checks and dynamic test data before approval.</p></article>
            <article><Icon name="shield" /><h3>Verify and run</h3><p>Check the script and requests before starting load. Watch throughput, latency, errors, and dropped iterations.</p></article>
            <article><Icon name="dashboard" /><h3>Compare releases</h3><p>See which thresholds passed, compare against an approved baseline, and share the report with your team.</p></article>
          </div>
        </section>
      </main>}
      <footer className="public-footer public-width">
        <a href="/" className="public-brand"><span className="sb-logo" aria-hidden="true"><i /><i /><i /></span>PerfAgent</a>
        <a href="/demo">Try with sample data <span aria-hidden="true">↗</span></a>
      </footer>
    </div>
  )
}
