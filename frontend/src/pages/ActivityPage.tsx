import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'

export function ActivityPage() {
return <>
<section className={"view"} id={"view-activity"}>
<div className={"viewwrap"}>
<div className={"card"}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px"} as CSSProperties}>
<h2 style={{"margin": "0", "fontSize": "14px"} as CSSProperties}>
{"Activity log"}
</h2>
<button className={"btn ghost sm"} onClick={handlers.h94}>
{"↻ Refresh"}
</button>
<span className={"muted"}>
{"who did what, when — for debugging & audit"}
</span>
</div>
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
<div className={"card"}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px"} as CSSProperties}>
<h2 style={{"margin": "0", "fontSize": "14px"} as CSSProperties}>
{"AI call traces"}
</h2>
<button className={"btn ghost sm"} onClick={handlers.h95}>
{"↻ Refresh"}
</button>
<span className={"muted"}>
{"each AI call — step, model, tokens, latency, status (for debugging)"}
</span>
</div>
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
</section>
</>
}
