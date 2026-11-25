import { useEffect, useState } from 'react'
import { Icon } from '../components/Icon'
import prism from '../assets/release-prism.jpg'
import report from '../../../docs/screenshots/release-comparison.png'
import dashboard from '../../../docs/screenshots/release-dashboard.png'
import './landing.css'

export function LandingPage({ page = 'landing' }: { page?: 'landing' | 'sign-in' | 'sign-up' }) {
  const access = page !== 'landing'
  const signup = page === 'sign-up'

  useEffect(() => {
    function focusSection() {
      const hash = window.location.hash
      if (hash !== '#workflow' && hash !== '#product') return
      const section = document.getElementById(hash.slice(1))
      section?.focus({ preventScroll: true })
      section?.scrollIntoView({ block: 'start', behavior: 'instant' })
    }

    focusSection()
    window.addEventListener('hashchange', focusSection)
    return () => window.removeEventListener('hashchange', focusSection)
  }, [page])
  const [showDashboard, setShowDashboard] = useState(false)
  const [budget, setBudget] = useState(10)
  const baseline = 100
  const candidate = 120
  const change = ((candidate - baseline) / baseline) * 100
  const withinBudget = change <= budget
  return (
    <div className="public-site">
      <a className="skip-link" href="#product">Skip to content</a>
      <header className="public-nav public-width">
        <a href="/" className="public-brand"><span className="sb-logo" aria-hidden="true"><i /><i /><i /></span>PerfAgent</a>
        <nav aria-label="Main navigation">
          <a className="public-nav-workflow" href={access ? '/#workflow' : '#workflow'}>How it works</a>
          <a href="/sign-in">Sign in</a>
          <a className="public-nav-signup" href="/sign-up">Get access <span aria-hidden="true">↗</span></a>
        </nav>
      </header>
      {access ? <main id="product" tabIndex={-1} className="public-access public-width">
        <section aria-labelledby="access-title">
          <span className="public-access-icon"><Icon name="shield" /></span>
          <h1 id="access-title">{signup ? 'Get access to PerfAgent' : 'Sign in to PerfAgent'}</h1>
          <p>{signup
            ? 'Ask your organization’s PerfAgent administrator for a workspace invitation. Once invited, sign in with your organization account.'
            : 'Use the organization account from your invitation and complete multi-factor sign-in when prompted.'}</p>
          <div className="public-actions">
            <a className="public-primary" href={signup ? '/sign-in' : '/workspace'}>{signup ? 'Sign in with your invitation' : 'Continue to workspace'} <span aria-hidden="true">↗</span></a>
            <a className="public-secondary" href="/demo">Try the demo</a>
          </div>
          {!signup && <p className="public-access-note"><a href="/sign-up">Need a workspace invitation?</a></p>}
        </section>
        <div className="public-access-art" aria-hidden="true">
          <img src={prism} alt="" width="1536" height="1024" />
        </div>
      </main> : <main id="product" tabIndex={-1}>
        <section className="public-hero public-width" aria-labelledby="public-title">
          <div className="public-intro">
            <h1 id="public-title">Catch regressions <em>before release.</em></h1>
            <p>Turn an endpoint or API spec into a k6 test. Verify what it sends, watch it run, and see what changed between releases.</p>
            <div className="public-actions">
              <a className="public-primary" href="/demo">Try the demo <span aria-hidden="true">↗</span></a>
              <a className="public-secondary" href="#workflow">Explore the workflow <span aria-hidden="true">↓</span></a>
            </div>
          </div>
          <div className="public-hero-art" aria-hidden="true">
            <img src={prism} alt="" width="1536" height="1024" fetchPriority="high" />
          </div>
        </section>
        <section className="public-product-proof public-width" aria-labelledby="public-proof-title">
          <div>
            <h2 id="public-proof-title">A passing test can still block a release.</h2>
            <p>A candidate can meet its k6 thresholds while running slower than the approved baseline. Compare both results before deciding whether to ship.</p>
            <a href="/demo?view=report">Open the sample comparison <span aria-hidden="true">↗</span></a>
          </div>
          <figure className="public-report">
            <div className="public-report-bar">
              <div className="public-preview-switch" role="group" aria-label="Product preview">
                <button type="button" aria-pressed={!showDashboard} onClick={() => setShowDashboard(false)}>Release report</button>
                <button type="button" aria-pressed={showDashboard} onClick={() => setShowDashboard(true)}>Dashboard</button>
              </div>
              <strong>Sample data</strong>
            </div>
            <img id="public-preview" src={showDashboard ? dashboard : report} loading="lazy" alt={showDashboard
              ? 'PerfAgent dashboard with historical performance and release readiness.'
              : 'PerfAgent release report comparing a sample candidate with its approved baseline.'} />
            <figcaption>{showDashboard
              ? 'Track latency and results across saved runs.'
              : 'Compare a candidate against an approved baseline.'}</figcaption>
          </figure>
        </section>
        <section className="public-workflow public-width" id="workflow" tabIndex={-1} aria-labelledby="public-workflow-title">
          <h2 id="public-workflow-title">From a target to a release decision</h2>
          <div className="public-steps">
            <article><Icon name="workspace" /><h3>Plan the workload</h3><p>Describe requests, set a traffic goal, and review the draft. Add response checks and dynamic test data before approval.</p><a href="/demo?view=review">Open a sample plan <span aria-hidden="true">↗</span></a></article>
            <article><Icon name="shield" /><h3>Verify and run</h3><p>Check the script and requests before starting load. Watch throughput, latency, errors, and dropped iterations.</p><a href="/demo?view=verify">Try sample verification <span aria-hidden="true">↗</span></a></article>
            <article><Icon name="dashboard" /><h3>Compare releases</h3><p>See which thresholds passed, compare against an approved baseline, and share the report with your team.</p><a href="/demo?view=report">See a sample report <span aria-hidden="true">↗</span></a></article>
          </div>
        </section>
        <section className="public-budget public-width" aria-labelledby="public-budget-title">
          <div className="public-budget-intro">
            <Icon name="dashboard" />
            <h2 id="public-budget-title">Would this release pass your latency budget?</h2>
            <p>Adjust the allowed increase in p95 latency. The sample uses the same candidate and baseline shown in the release report.</p>
            <a href="/demo">Explore the sample workspace <span aria-hidden="true">↗</span></a>
          </div>
          <div className="public-budget-card">
            <dl className="public-budget-metrics">
              <div><dt>Baseline p95</dt><dd>{baseline} <span>ms</span></dd></div>
              <div><dt>Candidate p95</dt><dd>{candidate} <span>ms</span></dd></div>
              <div><dt>Change</dt><dd>+{change}<span>%</span></dd></div>
            </dl>
            <label htmlFor="public-budget-limit">Allowed p95 increase <span>{budget}%</span></label>
            <input id="public-budget-limit" type="range" min={0} max={40} value={budget}
              aria-valuetext={budget + ' percent'} onChange={event => setBudget(event.currentTarget.valueAsNumber)} />
            <p className="public-budget-result" data-met={withinBudget} role="status">
              <strong>{withinBudget ? 'Budget met' : 'Budget breached'}</strong>
              <span>+{change}% measured · {budget}% allowed</span>
            </p>
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
