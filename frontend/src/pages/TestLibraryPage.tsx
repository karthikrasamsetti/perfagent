import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'

export function TestLibraryPage() {
return <>
<section className={"view"} id={"view-history"}>
<div className={"viewwrap"}>
<div className={"card"}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px"} as CSSProperties}>
<h2 style={{"margin": "0", "fontSize": "14px"} as CSSProperties}>
{"Saved plans"}
</h2>
<button className={"btn ghost sm"} onClick={handlers.h91}>
{"↻ Refresh"}
</button>
</div>
<table id={"plansTable"} style={{"marginTop": "10px"} as CSSProperties}>
<thead>
<tr>
<th>
{"Created"}
</th>
<th>
{"Target"}
</th>
<th>
{"Goal"}
</th>
<th>
{"Scripts"}
</th>
<th>

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
{"Runs & reports"}
</h2>
<button className={"btn ghost sm"} onClick={handlers.h92}>
{"↻ Refresh"}
</button>
<span className={"muted"}>
{"every finished run — click to reopen its report"}
</span>
</div>
<table id={"runsTable"} style={{"marginTop": "10px"} as CSSProperties}>
<thead>
<tr>
<th>
{"When"}
</th>
<th>
{"Verdict"}
</th>
<th>
{"Target"}
</th>
<th>
{"Test / script"}
</th>
<th>
{"Requests"}
</th>
<th>
{"Errors"}
</th>
<th>
{"p95"}
</th>
<th>

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
