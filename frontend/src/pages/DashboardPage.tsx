import type { CSSProperties } from 'react'
import { handlers, openDashboardTrendPoint, refreshDashboardTrend } from '../workspace/controller'

export function DashboardPage() {
return <>
<section className={"view"} id={"view-dashboard"}>
<div className={"viewwrap"}>
<div className={"project-context"} id={"projectDashboardSummary"} role={"status"}>

</div>
<div className="card dashboard-results">
<div className="section-header dashboard-heading">
<h2>Performance overview</h2>
<button className={"btn ghost sm"} onClick={handlers.h79}>
{"↻ Refresh"}
</button>
<div className={"spacer"}>

</div>
<label htmlFor={"sdRole"} style={{"margin": "0", "fontSize": "12px"} as CSSProperties}>
{"View as"}
</label>
<select id={"sdRole"} style={{"width": "auto", "padding": "5px 9px"} as CSSProperties} onChange={handlers.h80}>
<option value={"executive"}>
{"Executive"}
</option>
<option value={"qa_lead"}>
{"QA lead"}
</option>
<option value={"engineer"}>
{"Engineer"}
</option>
<option value={"viewer"}>
{"Viewer"}
</option>
</select>
</div>
<details className="dashboard-filters">
<summary>Filters</summary>
<div className="grid3">
<div className={"field"}>
<label htmlFor={"sdTest"}>
{"Test / workload"}
</label>
<select id={"sdTest"} onChange={handlers.h81}>
<option value={""}>
{"All tests"}
</option>
</select>
</div>
<div className={"field"}>
<label htmlFor={"sdTarget"}>
{"Target contains"}
</label>
<input id={"sdTarget"} type={"search"} placeholder={"Filter targets"} onInput={handlers.h82} />
</div>
<div className={"field"}>
<label htmlFor={"sdVerdict"}>
{"Verdict"}
</label>
<select id={"sdVerdict"} onChange={handlers.h83}>
<option value={""}>
{"All verdicts"}
</option>
<option value={"pass"}>
{"Pass"}
</option>
<option value={"fail"}>
{"Fail"}
</option>
<option value={"inconclusive"}>
{"Inconclusive"}
</option>
</select>
</div>
<div className={"field"}>
<label htmlFor="sdEnvironment">Environment</label>
<input id="sdEnvironment" type="search" maxLength={120} placeholder="e.g. staging" onInput={handlers.h82} />
</div>
<div className={"field"}>
<label htmlFor="sdRelease">Release</label>
<input id="sdRelease" type="search" maxLength={120} placeholder="e.g. v2.4.0" onInput={handlers.h82} />
</div>
<div className={"field"}>
<label htmlFor={"sdFrom"}>
{"From date"}
</label>
<input type={"date"} id={"sdFrom"} onChange={handlers.h84} />
</div>
<div className={"field"}>
<label htmlFor={"sdTo"}>
{"Through date"}
</label>
<input type={"date"} id={"sdTo"} onChange={handlers.h85} />
</div>
</div>
<div className={"btnrow"}>
<button className={"btn ghost sm"} onClick={handlers.h86}>
{"Clear filters"}
</button>
<span className={"muted"} id={"sdFilterNote"} role={"status"}>
{"Totals include all matching saved runs. Trends show up to 120 recent matches."}
</span>
</div>
</details>
<div className={"tiles"} id={"sdTiles"} style={{"gridTemplateColumns": "repeat(4,1fr)", "margin": "14px 0 4px"} as CSSProperties}>

</div>
<p className="muted dashboard-scope" id="sdActiveScope" />
<div className="dashboard-findings">
<section className="dashboard-attention" id="sdAttention" aria-label="Run to review" />
<section className="dashboard-attention" id="sdRegression" aria-label="Regression from baseline" hidden />
</div>
<section className="dashboard-history-charts" aria-label="Workload metrics and daily outcomes">
  <div className="dashboard-chart-header">
    <div><h3>Performance over time</h3><p className="muted" id="sdWorkloadScope" /></div>
    <button className="btn ghost sm" id="sdInspectReport" type="button">Open selected run</button>
  </div>
  <div className="report-sample-picker results-sample-picker">
    <label htmlFor="sdInspectRun">Inspect a run</label>
    <input id="sdInspectRun" type="range" min="0" step="1" />
    <output id="sdInspectRunNote" htmlFor="sdInspectRun" />
  </div>
  <div className="dashboard-chart-grid">
    <figure><figcaption>Latency (ms)</figcaption><p className="hint" id="sdLatencyLegend">p50 teal · p95 purple · p99 amber</p><canvas id="sdLatency" role="img" aria-label="Latency percentiles across comparable runs" /></figure>
    <figure><figcaption>Throughput (req/s)</figcaption><p className="hint">Achieved teal · target purple</p><canvas id="sdThroughput" role="img" aria-label="Achieved and target throughput across comparable runs" /></figure>
    <figure><figcaption>Error rate (%)</figcaption><canvas id="sdErrors" role="img" aria-label="Error rate across comparable runs" /></figure>
    <figure><figcaption>Run outcomes by day (UTC)</figcaption><div id="sdOutcomes" /></figure>
  </div>
</section>
<details className="dashboard-trend" aria-labelledby="sdTrendTitle">
  <summary id="sdTrendTitle">Trend data and report links</summary>
  <div className="section-header">
    <div className="dashboard-trend-control">
      <label htmlFor="sdTrendMetric">Metric</label>
      <select id="sdTrendMetric" onChange={refreshDashboardTrend} defaultValue="p95_ms">
        <option value="p50_ms">p50 latency</option>
        <option value="p95_ms">p95 latency</option>
        <option value="p99_ms">p99 latency</option>
        <option value="error_rate">Error rate</option>
        <option value="rps">Throughput</option>
        <option value="target_rps">Target throughput</option>
      </select>
    </div>
  </div>
  <p id="sdTrendCaption" className="muted" />
  <canvas id="sdTrend" role="img" aria-label="Performance trend" aria-describedby="sdTrendCaption"
    height={150} onClick={event => openDashboardTrendPoint(event.clientX)} />
  <div id="sdTrendData" className="table-scroll" />
</details>
<h3 className="dashboard-history-title">Recent runs</h3>
<div className={"table-scroll"} role={"region"} aria-label={"Recent runs"} tabIndex={0}>
<table id={"sdTable"} style={{"marginTop": "4px"} as CSSProperties}>
<thead>
<tr id={"sdHead"}>

</tr>
</thead>
<tbody>

</tbody>
</table>
</div>
<div className={"btnrow"}>
<button className={"btn ghost sm"} id={"sdPrev"} onClick={handlers.h89}>
{"Previous"}
</button>
<span className={"muted"} id={"sdPage"} role={"status"}>

</span>
<button className={"btn ghost sm"} id={"sdNext"} onClick={handlers.h90}>
{"Next"}
</button>
</div>
<div className={"muted"} id={"sdEmpty"} style={{"display": "none", "padding": "10px 2px"} as CSSProperties}>
{"No runs recorded yet. Run a plan to populate this."}
</div>
<details className="dashboard-compare">
<summary>Compare saved runs</summary>
<div className={"grid2"}>
<div className={"field"}>
<label htmlFor={"sdCompareA"}>
{"Baseline run"}
</label>
<select id={"sdCompareA"} onChange={handlers.h87}>

</select>
</div>
<div className={"field"}>
<label htmlFor={"sdCompareB"}>
{"Comparison run"}
</label>
<select id={"sdCompareB"} onChange={handlers.h88}>

</select>
</div>
</div>
<div id={"sdComparison"} className={"table-scroll"} aria-live={"polite"}>

</div>
</details>

</div>
</div>
</section>
</>
}
