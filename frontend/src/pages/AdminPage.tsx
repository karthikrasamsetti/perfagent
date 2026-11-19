import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'

export function AdminPage() {
return <>
<section className={"view"} id={"view-admin"}>
<div className={"viewwrap"}>
<div className={"card"}>
<h2>
{"All-project overview"}
</h2>
<p className={"hint"}>
{"Administrator access is checked by the server. Enter the token configured as ADMIN_API_TOKEN; it stays in this page's memory."}
</p>
<div className={"field"}>
<label htmlFor={"adminToken"}>
{"Administrator token"}
</label>
<input id={"adminToken"} type={"password"} autoComplete={"off"} />
</div>
<div className={"btnrow"}>
<button className={"btn"} onClick={handlers.h11}>
{"Load overview"}
</button>
<button className={"btn ghost"} onClick={handlers.h12}>
{"Clear"}
</button>
</div>
<div id={"adminOverview"} role={"status"} style={{"marginTop": "20px"} as CSSProperties}>

</div>
</div>
</div>
</section>
</>
}
