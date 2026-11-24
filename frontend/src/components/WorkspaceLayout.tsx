import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'
import { ProjectsPage } from '../pages/ProjectsPage'
import { TestWorkspacePage } from '../pages/TestWorkspacePage'
import { DashboardPage } from '../pages/DashboardPage'
import { TestLibraryPage } from '../pages/TestLibraryPage'
import { MonitoringPage } from '../pages/MonitoringPage'
import { ActivityPage } from '../pages/ActivityPage'
import { AdminPage } from '../pages/AdminPage'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { WorkspaceDialogs } from './WorkspaceDialogs'

export function WorkspaceLayout() {
return <>
<div id={"appNotice"} role={"alert"} style={{"display": "none", "position": "fixed", "bottom": "20px", "right": "20px", "maxWidth": "min(480px,90vw)", "zIndex": "4000"} as CSSProperties} className={"note err"}>
<span id={"appNoticeText"}>

</span>
<button className={"btn ghost sm"} onClick={handlers.h116} aria-label={"Dismiss message"}>
{"Dismiss"}
</button>
</div>
<div className={"sb-backdrop"} id={"sbBackdrop"} onClick={handlers.h117}>

</div>
<a className="skip-link" href="#workspace-content" onClick={event => {
  event.preventDefault()
  document.getElementById('workspace-content')?.focus()
}}>Skip to content</a>
<div className={"app"} onKeyDown={event => {
  if (event.key === 'Escape' && document.getElementById('sidebar')?.classList.contains('mobopen')) {
    document.getElementById('sbBackdrop')?.click()
  }
}}>
<Sidebar />
<div className={"main"}>
<Topbar />
<main id="workspace-content" tabIndex={-1}>
<ProjectsPage />
<AdminPage />
<TestWorkspacePage />
<DashboardPage />
<TestLibraryPage />
<MonitoringPage />
<ActivityPage />
</main>
</div>
</div>
<WorkspaceDialogs />
</>
}
