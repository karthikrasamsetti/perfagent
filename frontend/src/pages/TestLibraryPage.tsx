import { Icon } from '../components/Icon'
import { handlers } from '../workspace/controller'

export function TestLibraryPage() {
  return (
    <section className="view" id="view-history">
      <div className="viewwrap project-workspace">
        <header className="project-workspace-intro workspace-page-heading">
          <button className="btn ghost sm" onClick={handlers.h97}>All projects</button>
          <h2 id="libraryProjectName">Project workspace</h2>
          <p id="libraryProjectDescription" />
          <div className="btnrow">
            <button className="btn" onClick={handlers.h4}><Icon name="add" /> Create test</button>
            <button className="btn ghost" onClick={handlers.h8}>Dashboard</button>
            <button className="btn ghost" onClick={handlers.h9}>Project settings</button>
          </div>
        </header>
        <div className="project-workspace-grid">
          <section className="card project-test-list" aria-labelledby="projectTestsTitle">
            <div className="section-header">
              <h3 id="projectTestsTitle">Test library</h3>
              <button className="btn ghost sm refresh-action" type="button" aria-label="Refresh project tests" title="Refresh project tests" onClick={handlers.h91}><Icon name="refresh" /></button>
            </div>
            <label htmlFor="projectTestSearch">Find a test</label>
            <input id="projectTestSearch" type="search" placeholder="Search by name, purpose, or target" />
            <p className="hint" id="projectTestListStatus" role="status" />
            <div className="table-scroll" role="region" aria-label="Project tests" tabIndex={0}>
              <table id="plansTable">
                <thead><tr><th scope="col">Test</th><th scope="col">Script history</th><th scope="col">Action</th></tr></thead>
                <tbody />
              </table>
            </div>
          </section>
          <section className="card project-framework" aria-labelledby="projectFrameworkTitle">
            <h3 id="projectFrameworkTitle">Git framework</h3>
            <dl className="project-framework-config" id="libraryFrameworkConfig" />
            <h4>Export layout preview</h4>
            <p className="hint">Based on saved tests. Use Import / sync Git to inspect the repository.</p>
            <div id="libraryFrameworkTree" className="project-framework-tree" />
            <div className="btnrow">
              <button className="btn ghost sm" onClick={handlers.h6}>Import / sync Git</button>
              <button className="btn ghost sm" onClick={handlers.h5}>Import script</button>
            </div>
          </section>
        </div>
        <details className="card project-reports">
          <summary>Runs &amp; reports</summary>
          <div className="btnrow"><button className="btn ghost sm refresh-action" type="button" aria-label="Refresh reports" title="Refresh reports" onClick={handlers.h92}><Icon name="refresh" /></button></div>
          <div className="table-scroll" role="region" aria-label="Project reports" tabIndex={0}>
            <table id="runsTable">
              <thead><tr><th scope="col">When</th><th scope="col">Verdict</th><th scope="col">Target</th><th scope="col">Test / script</th><th scope="col">Requests</th><th scope="col">Errors</th><th scope="col">p95</th><th scope="col">Open report</th></tr></thead>
              <tbody />
            </table>
          </div>
        </details>
      </div>
    </section>
  )
}
