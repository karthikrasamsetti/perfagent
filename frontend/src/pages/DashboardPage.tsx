import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'

export function DashboardPage() {
return <>
<section className={"view"} id={"view-dashboard"}>
<div className={"viewwrap"}>
<div className={"project-context"} id={"projectDashboardSummary"} role={"status"}>

</div>
<div className={"card"}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px", "flexWrap": "wrap"} as CSSProperties}>
<h2 style={{"margin": "0", "fontSize": "15px"} as CSSProperties}>
{"📊 Stakeholder dashboard"}
</h2>
<button className={"btn ghost sm"} onClick={handlers.h79}>
{"↻ Refresh"}
</button>
<span className={"muted"}>
{"what each role sees across all runs"}
</span>
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
<div className={"grid3"} style={{"marginTop": "20px"} as CSSProperties}>
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
{"Filters search saved runs. Summaries and charts show the current page."}
</span>
</div>
<div className={"tiles"} id={"sdTiles"} style={{"gridTemplateColumns": "repeat(4,1fr)", "margin": "14px 0 4px"} as CSSProperties}>

</div>
<div className={"dash-grid"}>
<div className={"dash-cell"}>
<h4>
{"p95 latency across runs"}
</h4>
<div className={"sub"}>
{"lower is better · amber line"}
</div>
<canvas id={"sdTrend"} height={"140"} style={{"width": "100%"} as CSSProperties}>

</canvas>
</div>
<div className={"dash-cell"}>
<h4>
{"Error rate across runs"}
</h4>
<div className={"sub"}>
{"percentage of failed requests · red line"}
</div>
<canvas id={"sdErrTrend"} height={"140"} style={{"width": "100%"} as CSSProperties}>

</canvas>
</div>
<div className={"dash-cell"}>
<h4>
{"Verdict breakdown"}
</h4>
<div className={"sub"}>
{"pass / fail / inconclusive"}
</div>
<canvas id={"sdDonut"} height={"140"} style={{"width": "100%"} as CSSProperties}>

</canvas>
</div>
<div className={"dash-cell"}>
<h4>
{"Latency percentiles (latest run)"}
</h4>
<div className={"sub"}>
{"p50 · p95 · p99 in ms"}
</div>
<canvas id={"sdBars"} height={"140"} style={{"width": "100%"} as CSSProperties}>

</canvas>
</div>
</div>
<div className={"mini"} style={{"marginTop": "18px"} as CSSProperties}>
{"Compare runs"}
</div>
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
<div className={"mini"} style={{"marginTop": "18px"} as CSSProperties}>
{"Recent runs"}
</div>
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
</div>
</div>
</section>
</>
}
