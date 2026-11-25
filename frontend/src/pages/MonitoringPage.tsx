import { useEffect, useState } from 'react'
import { useLocation } from 'react-router'
import { Icon } from '../components/Icon'
import { monAdd } from '../workspace/controller'

const tools = ['Grafana', 'Datadog', 'Prometheus', 'Kibana', 'New Relic', 'Custom']

function LocalMonitoring() {
  const [status, setStatus] = useState('Checking the PerfAgent metrics endpoint…')

  useEffect(() => {
    const lifecycle = new AbortController()
    let timer: number | undefined

    async function checkMetrics() {
      try {
        const response = await fetch('/api/metrics', {
          cache: 'no-store',
          signal: AbortSignal.any([lifecycle.signal, AbortSignal.timeout(5000)]),
        })
        const body = await response.text()
        if (!response.ok || !body.startsWith('# HELP perfagent_')) throw new Error('Metrics unavailable')
        const hasSamples = /^perfagent_request_duration_seconds_count\{/m.test(body)
        setStatus(hasSamples
          ? 'Metrics endpoint responding. k6 request samples are available.'
          : 'Metrics endpoint responding. Run a local k6 test to collect request samples.')
      } catch {
        if (!lifecycle.signal.aborted) setStatus('Metrics endpoint unavailable. Check that the PerfAgent backend is running.')
      } finally {
        if (!lifecycle.signal.aborted) timer = window.setTimeout(checkMetrics, 15000)
      }
    }

    void checkMetrics()
    return () => {
      lifecycle.abort()
      window.clearTimeout(timer)
    }
  }, [])

  return (
    <section className="card" aria-labelledby="monitorLocalTitle">
      <h3 id="monitorLocalTitle">Local monitoring</h3>
      <p role="status">{status}</p>
      <p className="hint">Use the Prometheus targets page to confirm scraping. If Grafana has no data, check the target and the dashboard time range.</p>
      <p><code>docker compose -f docker-compose.observability.yml up -d</code></p>
      <div className="btnrow">
        <a className="btn" href="http://127.0.0.1:3000/d/perfagent-live" target="_blank" rel="noopener noreferrer">Open Grafana live dashboard</a>
        <a className="btn ghost" href="http://127.0.0.1:9090/targets" target="_blank" rel="noopener noreferrer">Check Prometheus target</a>
      </div>
    </section>
  )
}

export function MonitoringPage() {
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)
  const { pathname } = useLocation()
  const showLocalMonitoring = local && pathname === '/monitoring' && document.documentElement.dataset.demo !== 'true'

  return (
    <section className="view" id="view-monitoring">
      <div className="viewwrap monitoring-workspace">
        <header className="workspace-page-heading">
          <h2>Dashboards</h2>
          <p>Keep your service dashboards close to your performance test results.</p>
        </header>
        {showLocalMonitoring && <LocalMonitoring />}
        <section className="card monitor-setup" aria-labelledby="monitorSetupTitle">
          <h3 id="monitorSetupTitle">Link a dashboard</h3>
          <p className="hint">Saved in this browser. Use a dashboard URL without access tokens or credentials.</p>
          <p className="hint">Dashboards open in a new tab. Use the embedded preview for dashboards that allow it.</p>
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
