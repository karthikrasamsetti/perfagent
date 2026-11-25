import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'

export function ActivityPage() {
return <>
<section className={"view"} id={"view-activity"}>
<div className="viewwrap activity-workspace">
<div className={"card"}>
<div className="section-header activity-section-heading">
<h2>
{"Activity log"}
</h2>
<button className="btn ghost sm refresh-action" type="button" aria-label="Refresh activity log" title="Refresh activity log" onClick={handlers.h94}>↻</button>
<span className={"muted"}>
{"Plan, script, and run events"}
</span>
</div>
<div className="table-scroll" role="region" aria-label="Activity log table" tabIndex={0}>
<table id={"auditTable"} style={{"marginTop": "10px"} as CSSProperties}>
<thead>
<tr>
<th>
{"When"}
</th>
<th>
{"Action"}
</th>
<th>
{"Target"}
</th>
<th>
{"Details"}
</th>
<th>
{"AI usage"}
</th>
</tr>
</thead>
<tbody>

</tbody>
</table>
</div>
</div>
<div className={"card"}>
<div className="section-header activity-section-heading">
<h2>
{"AI call traces"}
</h2>
<button className="btn ghost sm refresh-action" type="button" aria-label="Refresh AI traces" title="Refresh AI traces" onClick={handlers.h95}>↻</button>
<span className={"muted"}>
{"Model, latency, token usage, and redaction counts"}
</span>
</div>
<div className="table-scroll" role="region" aria-label="AI call traces table" tabIndex={0}>
<table id={"tracesTable"} style={{"marginTop": "10px"} as CSSProperties}>
<thead>
<tr>
<th>
{"When"}
</th>
<th>
{"Step"}
</th>
<th>
{"Model"}
</th>
<th>
{"Tokens"}
</th>
<th>
{"Latency"}
</th>
<th>
{"Redactions"}
</th>
<th>
{"Status"}
</th>
</tr>
</thead>
<tbody>

</tbody>
</table>
</div>
</div>
</div>
</section>
</>
}
