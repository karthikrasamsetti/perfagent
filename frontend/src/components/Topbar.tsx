import { Icon } from './Icon'
import { WorkspaceAccount } from './WorkspaceAccount'
import { GuidedTour } from './GuidedTour'
import { handlers } from '../workspace/controller'

export function Topbar() {
  return (
    <header className="maintop">
      <button className="mobnav" id="mobileNavButton" onClick={handlers.h106} aria-label="Open navigation"
        aria-expanded="false" aria-controls="sidebar"><Icon name="activity" /></button>
      <div className="maintop-heading">
        <h1 id="viewTitle">Projects</h1>
        <p className="sub" id="viewSub">Organize performance tests by application.</p>
      </div>
      <div className="maintop-actions">
        {document.documentElement.dataset.tour !== 'true' && <GuidedTour />}
        <select id="projectPicker" aria-label="Switch project" onChange={handlers.h107}>
          <option value="">Select project</option>
        </select>
        <WorkspaceAccount />
      </div>
    </header>
  )
}
