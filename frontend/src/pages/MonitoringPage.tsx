import { Icon } from '../components/Icon'
import { monAdd } from '../workspace/controller'

const tools = ['Grafana', 'Datadog', 'Prometheus', 'Kibana', 'New Relic', 'Custom']

export function MonitoringPage() {
  return (
    <section className="view" id="view-monitoring">
      <div className="viewwrap monitoring-workspace">
        <header className="workspace-page-heading">
          <h2>Dashboards</h2>
          <p>Keep your service dashboards close to your performance test results.</p>
        </header>
        <section className="card monitor-setup" aria-labelledby="monitorSetupTitle">
          <h3 id="monitorSetupTitle">Link a dashboard</h3>
          <p className="hint">Saved in this browser. Use a dashboard URL without access tokens or credentials.</p>
          <form onSubmit={event => { event.preventDefault(); monAdd() }}>
            <div className="field">
              <label htmlFor="monTool">Tool</label>
              <select id="monTool">{tools.map(tool => <option key={tool}>{tool}</option>)}</select>
            </div>
            <div className="field">
              <label htmlFor="monUrl">Dashboard URL</label>
              <input id="monUrl" type="url" required maxLength={2048} placeholder="https://grafana.example.com/d/services" autoComplete="off" />
            </div>
            <button type="submit" className="btn"><Icon name="add" /> Link dashboard</button>
          </form>
          <p className="statusline" id="monStatus" role="status" />
        </section>
        <section aria-labelledby="monitorSavedTitle">
          <h3 id="monitorSavedTitle" className="section-heading">Linked dashboards</h3>
          <div id="monList" />
        </section>
      </div>
    </section>
  )
}
