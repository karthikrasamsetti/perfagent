import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'

export function MonitoringPage() {
return <>
<section className={"view"} id={"view-monitoring"}>
<div className={"viewwrap"}>
<div className={"card"}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px", "flexWrap": "wrap"} as CSSProperties}>
<h2 style={{"margin": "0", "fontSize": "15px"} as CSSProperties}>
{"📡 Monitoring tools"}
</h2>
<span className={"muted"}>
{"link your own Grafana, Datadog, Prometheus or any dashboard — it embeds here"}
</span>
</div>
<p className={"hint"} style={{"margin": "10px 0 0"} as CSSProperties}>
{"Add the URL of a dashboard you already run. It is stored only in this browser. If the tool blocks embedding, use "}
<b>
{"Open ↗"}
</b>
{" to view it in a new tab. For Grafana embedding, the Grafana admin must set "}
<code className={"k"}>
{"allow_embedding = true"}
</code>
{"."}
</p>
<div className={"grid3"} style={{"marginTop": "14px"} as CSSProperties}>
<div className={"field"}>
<label>
{"Tool"}
</label>
<select id={"monTool"}>
<option>
{"Grafana"}
</option>
<option>
{"Datadog"}
</option>
<option>
{"Prometheus"}
</option>
<option>
{"Kibana"}
</option>
<option>
{"New Relic"}
</option>
<option>
{"Custom"}
</option>
</select>
</div>
<div className={"field"} style={{"gridColumn": "span 2"} as CSSProperties}>
<label>
{"Dashboard URL"}
</label>
<input id={"monUrl"} placeholder={"https://grafana.mycompany.com/d/abc/perf?kiosk"} autoComplete={"off"} />
</div>
</div>
<div className={"btnrow"}>
<button className={"btn"} onClick={handlers.h93}>
{"+ Add dashboard"}
</button>
<span className={"hint"} style={{"margin": "0"} as CSSProperties}>
{"Tip: append "}
<code className={"k"}>
{"&kiosk"}
</code>
{" to a Grafana URL to hide its menus."}
</span>
</div>
<div className={"statusline"} id={"monStatus"}>

</div>
</div>
<div id={"monList"}>

</div>
</div>
</section>
</>
}
