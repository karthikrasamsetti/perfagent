import { handlers } from '../workspace/controller'

const sections = [
  {
    label: 'Workspace',
    items: [
      { label: 'Projects', icon: '▦', view: 'projects', onClick: handlers.h97 },
      { label: 'Create test', icon: '+', view: 'create', onClick: handlers.h98 },
      { label: 'Project workspace', icon: '▤', view: 'history', onClick: handlers.h102 },
    ],
  },
  {
    label: 'Results',
    items: [
      { label: 'Dashboard', icon: '▥', view: 'dashboard', onClick: handlers.h101 },
      { label: 'Monitoring', icon: '◉', view: 'monitoring', onClick: handlers.h103 },
      { label: 'Activity', icon: '≡', view: 'activity', onClick: handlers.h104 },
    ],
  },
  {
    label: 'Tools',
    items: [
      { label: 'Import script', icon: '↥', onClick: handlers.h99 },
      { label: 'Git framework', icon: '⑂', onClick: handlers.h100 },
      { label: 'Administration', icon: '⚙', view: 'admin', onClick: handlers.h105 },
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
          aria-label="Collapse sidebar" aria-expanded="true" aria-controls="sidebar">«</button>
        <button className="sb-mobile-close" onClick={handlers.h117} aria-label="Close navigation">×</button>
      </div>
      <div className="sb-nav">
        {sections.map(section => (
          <div className="sb-group" key={section.label}>
            <div className="sb-group-label">{section.label}</div>
            {section.items.map(item => (
              <button key={item.label} className={'sb-item' + (item.view === 'projects' ? ' active' : '')}
                data-view={item.view} aria-label={item.label}
                aria-current={item.view === 'projects' ? 'page' : undefined} onClick={item.onClick}>
                <span className="sb-ic" aria-hidden="true">{item.icon}</span>
                <span className="sb-lbl">{item.label}</span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </nav>
  )
}
