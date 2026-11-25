import { Icon } from './Icon'
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
        <select id="projectPicker" aria-label="Switch project" onChange={handlers.h107}>
          <option value="">Select project</option>
        </select>
        <div className="usage-chip" id="sessionUsage" title="Estimated AI usage for this session">
          <span>AI usage</span>
          <strong id="sessionTokens">0</strong>
          <span>tokens</span>
          <span id="sessionCost" />
        </div>
      </div>
    </header>
  )
}
