import { Icon } from './Icon'
import { handlers, showView } from '../workspace/controller'

const sections = [
  {
    label: 'Workspace',
    items: [
      { label: 'Home', icon: 'home' as const, view: 'home', onClick: () => showView('home') },
      { label: 'Projects', icon: 'projects' as const, view: 'projects', onClick: handlers.h97 },
      { label: 'Create test', icon: 'add' as const, view: 'create', onClick: handlers.h98 },
      { label: 'Project workspace', icon: 'workspace' as const, view: 'history', onClick: handlers.h102 },
    ],
  },
  {
    label: 'Results',
    items: [
      { label: 'Dashboard', icon: 'dashboard' as const, view: 'dashboard', onClick: handlers.h101 },
      { label: 'Monitoring', icon: 'pulse' as const, view: 'monitoring', onClick: handlers.h103 },
      { label: 'Activity', icon: 'activity' as const, view: 'activity', onClick: handlers.h104 },
    ],
  },
  {
    label: 'Tools',
    items: [
      { label: 'Import script', icon: 'upload' as const, onClick: handlers.h99 },
      { label: 'Git framework', icon: 'git' as const, onClick: handlers.h100 },
      { label: 'Administration', icon: 'shield' as const, view: 'admin', onClick: handlers.h105 },
    ],
  },
]

export function Sidebar() {
  return (
    <nav className="sidebar" id="sidebar" aria-label="Main navigation" onKeyDown={event => {
      if (event.key !== 'Tab' || !event.currentTarget.classList.contains('mobopen')) return
      const items = Array.from(event.currentTarget.querySelectorAll('button')).filter(button => button.offsetWidth > 0)
      const first = items[0], last = items[items.length - 1]
      if (event.shiftKey && event.target === first) { event.preventDefault(); last?.focus() }
      if (!event.shiftKey && event.target === last) { event.preventDefault(); first?.focus() }
    }}>
      <div className="sb-top">
        <div className="sb-logo" aria-hidden="true"><i /><i /><i /></div>
        <span className="sb-title">PerfAgent</span>
        <button className="sb-toggle" onClick={handlers.h96} title="Collapse sidebar"
          aria-label="Collapse sidebar" aria-expanded="true" aria-controls="sidebar"><Icon name="collapse" /></button>
        <button className="sb-mobile-close" onClick={handlers.h117} aria-label="Close navigation"><Icon name="close" /></button>
      </div>
      <div className="sb-nav">
        {sections.map(section => (
          <div className="sb-group" key={section.label}>
            <div className="sb-group-label">{section.label}</div>
            {section.items.map(item => (
              <button key={item.label} className={'sb-item' + (item.view === 'projects' ? ' active' : '')}
                data-view={item.view} aria-label={item.label}
                aria-current={item.view === 'projects' ? 'page' : undefined} onClick={item.onClick}>
                <span className="sb-ic" aria-hidden="true"><Icon name={item.icon} /></span>
                <span className="sb-lbl">{item.label}</span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </nav>
  )
}
