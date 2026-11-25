import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router'
import { BrandMark } from '../components/BrandMark'
import { Icon } from '../components/Icon'
import prism from '../assets/release-prism.jpg'
import report from '../../../docs/screenshots/release-comparison.png'
import dashboard from '../../../docs/screenshots/release-dashboard.png'
import './landing.css'

export function LandingPage({ page, loginHandoff }: {
  page: 'landing' | 'sign-in' | 'sign-up'
  loginHandoff: boolean
}) {
  const { hash, key } = useLocation()
  const access = page !== 'landing'
  const signup = page === 'sign-up'
  const story = useRef<HTMLElement>(null)
  const hero = useRef<HTMLElement>(null)
  const proof = useRef<HTMLElement>(null)

  useEffect(() => {
    const element = story.current
    const heroSection = hero.current
    const proofSection = proof.current
    if (!element || !heroSection || !proofSection) return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    let frame = 0

    function positionArtwork() {
      frame = 0
      if (!element || !heroSection || !proofSection || reduceMotion.matches) return
      const clamp = (value: number) => Math.max(0, Math.min(1, value))
      const heroBox = heroSection.getBoundingClientRect()
      const proofBox = proofSection.getBoundingClientRect()
      const compact = window.innerWidth <= 820
      const drift = clamp(-heroBox.top / heroBox.height)
      const entry = 1 - clamp((window.innerHeight - proofBox.top) / (window.innerHeight * .58))
      element.style.setProperty('--prism-offset', (drift * (compact ? 27 : 70)).toFixed(2) + 'px')
      element.style.setProperty('--prism-zoom', (1 + drift * .21).toFixed(3))
      element.style.setProperty('--preview-offset', (entry * (compact ? 26 : 64)).toFixed(2) + 'px')
      element.style.setProperty('--preview-scale', (1 - entry * .08).toFixed(3))
      element.style.setProperty('--atmosphere-offset', (entry * -42).toFixed(2) + 'px')
    }

    function update() {
      if (!frame) frame = requestAnimationFrame(positionArtwork)
    }

    function updatePreference() {
      if (!element) return
      element.toggleAttribute('data-motion', !reduceMotion.matches)
      update()
    }

    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    reduceMotion.addEventListener('change', updatePreference)
    updatePreference()
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
      reduceMotion.removeEventListener('change', updatePreference)
      cancelAnimationFrame(frame)
      element.removeAttribute('data-motion')
    }
  }, [page])

  useEffect(() => {
    const id = hash === '#workflow' ? 'workflow' : 'product'
    const target = document.getElementById(id)
    if (hash || key !== 'default') target?.focus({ preventScroll: true })
    if (hash) target?.scrollIntoView({ block: 'start', behavior: 'instant' })
    else window.scrollTo({ top: 0, behavior: 'instant' })
  }, [hash, key])
  const [showDashboard, setShowDashboard] = useState(false)
  const [budget, setBudget] = useState(10)
  const baseline = 100
  const candidate = 120
  const change = ((candidate - baseline) / baseline) * 100
  const withinBudget = change <= budget
  return (
    <div className="public-site">
      <Link className="skip-link" to="#product">Skip to content</Link>
      <header className="public-nav public-width">
        <Link to="/" className="public-brand"><BrandMark />PerfAgent</Link>
        <nav aria-label="Main navigation">
          <Link className="public-nav-workflow" to="/#workflow">How it works</Link>
          <Link to="/sign-in" aria-current={page === 'sign-in' ? 'page' : undefined}>Sign in</Link>
          <Link className="public-nav-signup" to="/sign-up" aria-current={signup ? 'page' : undefined}>Get access <span aria-hidden="true">↗</span></Link>
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
            <Link className="public-primary" to={signup ? '/sign-in' : '/workspace'} reloadDocument={!signup && loginHandoff}>{signup ? 'Sign in with your invitation' : 'Continue to workspace'} <span aria-hidden="true">↗</span></Link>
            <a className="public-secondary" href="/demo">Try the demo</a>
          </div>
          <details className="public-access-help">
            <summary>{signup ? 'How do I get invited?' : 'Having trouble signing in?'}</summary>
            <p>{signup
              ? 'Ask your administrator to invite the same organization account you’ll use to sign in.'
              : 'Use the account listed in your invitation. If the invitation expired or you used a different account, ask your administrator to resend it.'}</p>
            {!signup && <Link to="/sign-up">View invitation steps <span aria-hidden="true">↗</span></Link>}
          </details>
        </section>
        <a className="public-access-art" href="/demo?view=report">
          <img src={prism} alt="" width="1536" height="1024" />
          <span className="public-access-art-action">Explore a sample release <span aria-hidden="true">↗</span></span>
        </a>
      </main> : <main id="product" tabIndex={-1} className="public-story" ref={story}>
        <section className="public-hero public-width" ref={hero} aria-labelledby="public-title">
          <div className="public-intro">
            <h1 id="public-title">Catch regressions <em>before release.</em></h1>
            <p>Turn an endpoint or API spec into a k6 test. Verify what it sends, watch it run, and see what changed between releases.</p>
            <div className="public-actions">
              <a className="public-primary" href="/demo">Try the demo <span aria-hidden="true">↗</span></a>
              <Link className="public-secondary" to="#workflow">Explore the workflow <span aria-hidden="true">↓</span></Link>
            </div>
          </div>
          <div className="public-hero-art" aria-hidden="true">
            <img src={prism} alt="" width="1536" height="1024" fetchPriority="high" />
          </div>
        </section>
        <section className="public-product-proof public-width" ref={proof} aria-labelledby="public-proof-title">
          <div className="public-proof-atmosphere" aria-hidden="true"><img src={prism} alt="" loading="lazy" /></div>
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
        <Link to="/" className="public-brand"><BrandMark />PerfAgent</Link>
        <a href="/demo">Try with sample data <span aria-hidden="true">↗</span></a>
      </footer>
    </div>
  )
}
