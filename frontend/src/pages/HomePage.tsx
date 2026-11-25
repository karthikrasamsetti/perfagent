import { Link } from 'react-router'
import { demoRelease, demoReportPath, demoTestPath } from '../demo/fixtures'
import { Icon } from '../components/Icon'
import { openHomeAction } from '../workspace/controller'

export function HomePage() {
  const demo = document.documentElement.dataset.demo === 'true'
  const comparison = demo ? demoRelease : { baselineP95: 100, candidateP95: 120, maxIncreasePercent: 10 }
  const change = ((comparison.candidateP95 / comparison.baselineP95) - 1) * 100
  return (
    <section className="view" id="view-home" aria-label="PerfAgent home">
      <div className="viewwrap home-workspace">
        <header className="home-lead">
          <div className="home-intro">
            <h2>From first request<br />to <em>release decision.</em></h2>
            <p>{demo
              ? 'Verify the sample checkout, run a simulated workload, and see how its release compares against the approved baseline.'
              : 'Build a k6 workload, verify the requests it sends, and compare the results against your performance budgets.'}</p>
            <div className="btnrow">
              {demo ? <Link className="btn" to={demoTestPath + '?step=3'}>
                <Icon name="shield" /> Try the checkout test
              </Link> : <button type="button" className="btn" onClick={() => openHomeAction('create')}>
                <Icon name="add" /> Create a test
              </button>}
              <Link className="btn ghost" to="/projects"><Icon name="projects" /> Open projects</Link>
            </div>
          </div>
          <section className="home-comparison" aria-labelledby="homeComparisonTitle">
            <header>
              <Icon name="pulse" />
              <h3 id="homeComparisonTitle">Release comparison</h3>
              <span>Sample</span>
            </header>
            <dl>
              <div><dt>Baseline p95</dt><dd>{comparison.baselineP95} <span>ms</span></dd></div>
              <div><dt>Candidate p95</dt><dd>{comparison.candidateP95} <span>ms</span></dd></div>
            </dl>
            <footer><strong>Budget breached</strong><span>+{Number(change.toFixed(1))}% measured · {comparison.maxIncreasePercent}% allowed</span></footer>
          </section>
        </header>
        <section aria-labelledby="homeActionsTitle">
          <h3 className="section-heading" id="homeActionsTitle">Continue your work</h3>
          <div className="home-actions">
            <article>
              <span className="home-action-icon"><Icon name="upload" /></span>
              <div><h4>Import a k6 script</h4><p>Bring a script into a project, then verify it before running.</p>
                <button type="button" className="btn ghost sm" onClick={() => openHomeAction('import')}>Import script</button>
              </div>
            </article>
            <article>
              <span className="home-action-icon"><Icon name="dashboard" /></span>
              <div><h4>Review a release</h4><p>Compare results across runs and see where performance changed.</p>
                {demo ? <Link className="btn ghost sm" to={demoReportPath}>Open sample report</Link>
                  : <button type="button" className="btn ghost sm" onClick={() => openHomeAction('dashboard')}>Open dashboard</button>}
              </div>
            </article>
          </div>
        </section>
      </div>
    </section>
  )
}
