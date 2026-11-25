import { useEffect, useRef, useState } from 'react'
import { maxTrafficBytes, summarizeTraffic } from '../workspace/trafficSummary'

const example = 'window_start,window_seconds,method,route,requests\n2026-01-10T12:00:00Z,60,GET,/products,720\n2026-01-10T12:00:00Z,60,POST,/checkout,180\n2026-01-10T12:01:00Z,60,GET,/products,420\n2026-01-10T12:01:00Z,60,POST,/checkout,120'
const format = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 })

export function TrafficImport({ onApply }: { onApply: (rate: number) => void }) {
  const [summary, setSummary] = useState<ReturnType<typeof summarizeTraffic> | null>(null)
  const [status, setStatus] = useState('')
  const [basis, setBasis] = useState('peak')
  const fileInput = useRef<HTMLInputElement>(null)
  const latest = useRef(0)
  useEffect(() => {
    const reset = () => {
      latest.current++
      setSummary(null)
      setStatus('')
      setBasis('peak')
      if (fileInput.current) fileInput.current.value = ''
    }
    window.addEventListener('perfagent:reset-traffic', reset)
    return () => window.removeEventListener('perfagent:reset-traffic', reset)
  }, [])

  async function read(file: File | undefined) {
    const attempt = ++latest.current
    setSummary(null)
    setStatus('')
    if (!file) return
    try {
      if (file.size > maxTrafficBytes) throw new Error('Choose a CSV file up to 256 KiB.')
      const result = summarizeTraffic(await file.text())
      if (attempt === latest.current) {
        setSummary(result)
        setStatus('Traffic summary ready.')
      }
    } catch (error) {
      if (attempt === latest.current) setStatus(error instanceof Error ? error.message : 'Could not read the CSV.')
    }
  }

  const rate = summary && Math.max(1, Math.round(basis === 'peak' ? summary.peakRate : summary.meanRate))
  return <details className="traffic-import">
    <summary>Plan from sampled traffic</summary>
    <p className="hint">Import aggregate counts by route and time window. The file is read in this browser. Use route templates and omit customer identifiers, queries, headers, and request bodies.</p>
    <div className="field">
      <label htmlFor="trafficCsv">Traffic summary CSV</label>
      <input ref={fileInput} id="trafficCsv" type="file" accept=".csv,text/csv" onChange={event => void read(event.target.files?.[0])} />
    </div>
    <a download="traffic-example.csv" href={'data:text/csv;charset=utf-8,' + encodeURIComponent(example)}>Download example CSV</a>
    <p role="status">{status}</p>
    {summary && <div>
      <p><strong>{format.format(summary.peakRate)} req/s peak window</strong> · {format.format(summary.meanRate)} req/s average · {summary.windows} {summary.windows === 1 ? 'window' : 'windows'}</p>
      <div className="release-table" tabIndex={0} role="region" aria-label="Observed route mix">
        <table><thead><tr><th scope="col">Observed route</th><th scope="col">Requests</th><th scope="col">Share</th></tr></thead>
          <tbody>{summary.mix.slice(0, 15).map(({ route, count, share }) => <tr key={route}>
            <th scope="row">{route}</th><td>{format.format(count)}</td><td>{format.format(share * 100)}%</td>
          </tr>)}</tbody>
        </table>
      </div>
      {summary.mix.length > 15 && <p className="hint">Showing the 15 highest-volume routes out of {summary.mix.length}.</p>}
      <p className="hint">These shares describe observed requests. Define your endpoints and journey order below. PerfAgent converts the chosen request rate into a k6 journey rate after you draft the plan.</p>
      <div className="field">
        <label htmlFor="trafficRateBasis">Suggested rate basis</label>
        <select id="trafficRateBasis" value={basis} onChange={event => setBasis(event.target.value)}>
          <option value="peak">Busiest observed window</option>
          <option value="mean">Average across observed windows</option>
        </select>
      </div>
      <button type="button" className="btn ghost sm" disabled={!rate || rate > 1_000_000} onClick={() => {
        if (!rate) return
        onApply(rate)
        setStatus('Applied ' + rate + ' requests/s. Review the rate and virtual-user allocation before drafting.')
      }}>Use {rate} requests/s</button>
      {rate !== null && rate > 1_000_000 && <p className="hint">Enter a smaller request rate manually.</p>}
    </div>}
  </details>
}
