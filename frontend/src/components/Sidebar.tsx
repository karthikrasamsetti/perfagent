import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'

export function Sidebar() {
return <>
<nav className={"sidebar"} id={"sidebar"} aria-label={"Main navigation"}>
<div className={"sb-top"}>
<div className={"sb-logo"}>
{"⚡"}
</div>
<div className={"sb-title"}>
{"PerfAgent"}
</div>
<button className={"sb-toggle"} onClick={handlers.h96} title={"Collapse sidebar"} aria-label={"Collapse sidebar"} aria-expanded={"true"} aria-controls={"sidebar"}>
{"☰"}
</button>
</div>
<div className={"sb-nav"}>
<button className={"sb-item active"} data-view={"projects"} onClick={handlers.h97}>
<span className={"sb-ic"}>
{"▦"}
</span>
<span className={"sb-lbl"}>
{"Projects"}
</span>
</button>
<button className={"sb-item"} data-view={"create"} onClick={handlers.h98}>
<span className={"sb-ic"}>
{"🎯"}
</span>
<span className={"sb-lbl"}>
{"Create test"}
</span>
</button>
<button className={"sb-item"} onClick={handlers.h99}>
<span className={"sb-ic"}>
{"＋"}
</span>
<span className={"sb-lbl"}>
{"Import script"}
</span>
</button>
<button className={"sb-item"} onClick={handlers.h100}>
<span className={"sb-ic"}>
{"⑂"}
</span>
<span className={"sb-lbl"}>
{"Git framework"}
</span>
</button>
<button className={"sb-item"} data-view={"dashboard"} onClick={handlers.h101}>
<span className={"sb-ic"}>
{"📊"}
</span>
<span className={"sb-lbl"}>
{"Dashboard"}
</span>
</button>
<button className={"sb-item"} data-view={"history"} onClick={handlers.h102}>
<span className={"sb-ic"}>
{"📁"}
</span>
<span className={"sb-lbl"}>
{"History"}
</span>
</button>
<button className={"sb-item"} data-view={"monitoring"} onClick={handlers.h103}>
<span className={"sb-ic"}>
{"📡"}
</span>
<span className={"sb-lbl"}>
{"Monitoring"}
</span>
</button>
<button className={"sb-item"} data-view={"activity"} onClick={handlers.h104}>
<span className={"sb-ic"}>
{"📋"}
</span>
<span className={"sb-lbl"}>
{"Activity"}
</span>
</button>
<button className={"sb-item"} data-view={"admin"} onClick={handlers.h105}>
<span className={"sb-ic"}>
{"▤"}
</span>
<span className={"sb-lbl"}>
{"Admin overview"}
</span>
</button>
</div>
<div className={"sb-foot"}>
{"AI drafts · you approve · code runs"}
</div>
</nav>
</>
}
