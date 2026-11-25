import { Link } from 'react-router'
import { Icon } from '../components/Icon'
import { openHomeAction } from '../workspace/controller'

export function HomePage() {
  return (
    <section className="view" id="view-home" aria-label="PerfAgent home">
      <div className="viewwrap home-workspace">
        <header className="home-lead">
          <div>
            <h2>Know how your application performs under load.</h2>
            <p>Design a k6 workload, verify the requests it sends, and compare releases against your performance budgets.</p>
            <div className="btnrow">
              <button type="button" className="btn" onClick={() => openHomeAction('create')}>
                <Icon name="add" /> Create a test
              </button>
              <Link className="btn ghost" to="/projects"><Icon name="projects" /> Open projects</Link>
            </div>
          </div>
          <div className="home-flow" aria-label="Performance testing workflow">
            <div><Icon name="workspace" /><span><strong>Plan the workload</strong><small>Set requests, traffic, and success criteria</small></span></div>
            <div><Icon name="shield" /><span><strong>Review and verify</strong><small>Confirm test inputs before applying load</small></span></div>
            <div><Icon name="dashboard" /><span><strong>Compare the results</strong><small>See what changed across releases</small></span></div>
          </div>
        </header>
        <section aria-labelledby="homeActionsTitle">
          <h3 className="section-heading" id="homeActionsTitle">Pick up where you need to</h3>
          <div className="home-actions">
            <article>
              <Icon name="upload" /><h4>Bring an existing k6 script</h4>
              <p>Import a script into your project and review it before running.</p>
              <button type="button" className="btn ghost sm" onClick={() => openHomeAction('import')}>Import script</button>
            </article>
            <article>
              <Icon name="dashboard" /><h4>Review a release</h4>
              <p>Open your project dashboard to compare runs and investigate a regression.</p>
              <button type="button" className="btn ghost sm" onClick={() => openHomeAction('dashboard')}>Open dashboard</button>
            </article>
          </div>
        </section>
      </div>
    </section>
  )
}
