import { Icon } from '../components/Icon'
import type { CSSProperties } from 'react'
import { filterProjects, handlers } from '../workspace/controller'

export function ProjectsPage() {
return <>
<section className={"view show"} id={"view-projects"}>
<div className={"viewwrap"}>
<section className="projects-intro" aria-label="Project actions">
  <div>
    <h2>Performance workspace</h2>
    <p>Group tests, environments, and run history by application.</p>
  </div>
  <div className="btnrow">
    <button className="btn" onClick={handlers.h0}><Icon name="add" /> Create project</button>
    <button className="btn ghost" onClick={handlers.h1}><Icon name="git" /> Import from Git</button>
  </div>
</section>
<div id={"projectForm"} className={"card"} style={{"display": "none"} as CSSProperties}>
<h2 id={"projectFormTitle"}>
{"Create project"}
</h2>
<div className={"grid2"}>
<div className={"field"}>
<label htmlFor={"projectName"}>
{"Project name"}
</label>
<input id={"projectName"} maxLength={120} placeholder={"Commerce performance"} />
</div>
<div className={"field"}>
<label htmlFor={"projectFramework"}>
{"Framework folder"}
</label>
<input id={"projectFramework"} placeholder={"commerce-performance"} />
</div>
<div className={"field"}>
<label htmlFor={"projectTarget"}>
{"Default target URL"}
</label>
<input id={"projectTarget"} placeholder={"https://staging.example.com"} />
</div>
<div className={"field"}>
<label htmlFor={"projectEnvironment"}>
{"Default environment"}
</label>
<input id={"projectEnvironment"} defaultValue={"staging"} />
</div>
<div className={"field"}>
<label htmlFor={"projectRepo"}>
{"Git repository (optional)"}
</label>
<input id={"projectRepo"} placeholder={"https://github.com/org/performance-tests.git"} />
</div>
<div className={"field"}>
<label htmlFor={"projectBranch"}>
{"Git branch"}
</label>
<input id={"projectBranch"} defaultValue={"main"} />
</div>
</div>
<div className={"field"}>
<label htmlFor={"projectDescription"}>
{"Description"}
</label>
<textarea id={"projectDescription"} maxLength={2000}>

</textarea>
</div>
<div className={"field"}>
<label>
{"CI templates"}
</label>
<label className={"chk"}>
<input type={"checkbox"} className={"projectCi"} defaultValue={"jenkins"} defaultChecked />
{" Jenkins"}
</label>
<label className={"chk"}>
<input type={"checkbox"} className={"projectCi"} defaultValue={"github"} />
{" GitHub Actions"}
</label>
<label className={"chk"}>
<input type={"checkbox"} className={"projectCi"} defaultValue={"azure"} />
{" Azure Pipelines"}
</label>
<label className={"chk"}>
<input type={"checkbox"} className={"projectCi"} defaultValue={"gitlab"} />
{" GitLab CI"}
</label>
</div>
<div className={"btnrow"}>
<button className={"btn"} onClick={handlers.h2}>
{"Save project"}
</button>
<button className={"btn ghost"} onClick={handlers.h3}>
{"Cancel"}
</button>
</div>
<div id={"projectSaveStatus"} className={"statusline"} role={"status"}>

</div>
</div>
<div id={"activeProject"} className={"card"} style={{"display": "none"} as CSSProperties}>
<h2 id={"activeProjectName"}>

</h2>
<p className={"hint"} id={"activeProjectDescription"}>

</p>
<div className={"btnrow"}>
<button className={"btn"} onClick={handlers.h4}>
{"Create test"}
</button>
<button className={"btn ghost"} onClick={handlers.h5}>
{"Import script"}
</button>
<button className={"btn ghost"} onClick={handlers.h6}>
{"Import / sync Git"}
</button>
<button className={"btn ghost"} onClick={handlers.h7}>
{"Test library"}
</button>
<button className={"btn ghost"} onClick={handlers.h8}>
{"Project dashboard"}
</button>
<button className={"btn ghost"} onClick={handlers.h9}>
{"Settings"}
</button>
</div>
</div>
<div id={"newTestForm"} className={"card"} style={{"display": "none"} as CSSProperties}>
<h2>
{"Create a test"}
</h2>
<p className={"hint"}>
{"Name the journey first. You can save several workload profiles for the same test."}
</p>
<div className={"field"}>
<label htmlFor={"newTestName"}>
{"Test name"}
</label>
<input id={"newTestName"} maxLength={120} placeholder={"Checkout journey"} aria-describedby="newTestNameHint" />
<p className="hint" id="newTestNameHint">Use a unique name within this project.</p>
</div>
<div className={"field"}>
<label htmlFor={"newTestPurpose"}>
{"Purpose"}
</label>
<textarea id={"newTestPurpose"} placeholder={"Verify checkout meets expected traffic and response-time targets"}>

</textarea>
</div>
<div className={"btnrow"}>
<button className={"btn"} onClick={handlers.h10}>
{"Continue to test setup"}
</button>
</div>
</div>
<div className="section-header project-library-heading">
  <h2 className="section-heading">Project library</h2>
  <div className="project-library-search">
    <label className="sr-only" htmlFor="projectSearch">Search projects</label>
    <input type="search" id="projectSearch" placeholder="Search projects" onInput={filterProjects} />
  </div>
</div>
<p className="muted" id="projectSearchStatus" role="status" hidden />
<div id={"projectCards"} className={"project-grid"}>

</div>
</div>
</section>
</>
}
