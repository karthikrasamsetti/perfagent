import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'

export function Topbar() {
return <>
<div className={"maintop"}>
<button className={"mobnav"} onClick={handlers.h106} aria-label={"Open navigation"}>
{"☰"}
</button>
<div>
<h1 id={"viewTitle"}>
{"Create a performance test"}
</h1>
<div className={"sub"} id={"viewSub"}>
{"AI drafts the plan · you approve · code generates, runs & reports"}
</div>
</div>
<div style={{"flex": "1"} as CSSProperties}>

</div>
<select id={"projectPicker"} aria-label={"Current project"} style={{"width": "auto", "maxWidth": "220px"} as CSSProperties} onChange={handlers.h107}>
<option value={""}>
{"Select project"}
</option>
</select>
<div className={"usage-chip"} id={"sessionUsage"} title={"Total AI tokens used this session (rough cost estimate)"}>
{"\n        🪙 "}
<span id={"sessionTokens"}>
{"0"}
</span>
{" tokens\n        "}
<span id={"sessionCost"} style={{"opacity": ".8"} as CSSProperties}>

</span>
</div>
</div>
</>
}
