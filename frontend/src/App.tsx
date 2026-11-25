import { memo, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { GuidedTourOverlay } from './components/GuidedTour'
import { WorkspaceLayout } from './components/WorkspaceLayout'
import { applyRoute, dispose, initialize } from './workspace/controller'

const StableWorkspace = memo(WorkspaceLayout)

export function App() {
  const location = useLocation(), navigate = useNavigate()
  const [loading, setLoading] = useState(true), [error, setError] = useState('')
  const [restoredPath, setRestoredPath] = useState('')
  const requested = useRef(''), skip = useRef(''), running = useRef(false)
  const active = useRef(true), startup = useRef<Promise<void> | null>(null)
  const navigateRef = useRef(navigate)
  navigateRef.current = navigate

  useEffect(() => {
    active.current = true
    const onNavigate = (event: Event) => {
      const path = (event as CustomEvent<string>).detail
      if (path === window.location.pathname + window.location.search) return
      skip.current = path
      navigateRef.current(path)
    }
    window.addEventListener('perfagent:navigate', onNavigate)
    return () => { active.current = false; startup.current = null; window.removeEventListener('perfagent:navigate', onNavigate); dispose() }
  }, [])

  useEffect(() => {
    const path = location.pathname + location.search
    if (skip.current === path) { skip.current = ''; return }
    requested.current = path
    if (running.current) return
    running.current = true
    setLoading(true); setError('')
    async function restore() {
      try {
        if (!startup.current) startup.current = initialize()
        await startup.current
        while (active.current && requested.current) {
          const next = requested.current; requested.current = ''
          try { await applyRoute(next) }
          catch (cause) { if (!requested.current) throw cause }
          finally { if (active.current) setRestoredPath(next) }
        }
      } catch (cause) {
        if (active.current) setError(cause instanceof Error ? cause.message : 'This page could not be opened.')
      } finally {
        running.current = false
        if (active.current) setLoading(false)
      }
    }
    void restore()
  }, [location.pathname, location.search])

  const touring = document.documentElement.dataset.tour === 'true'
  useEffect(() => {
    if (!loading && !touring && window.location.hash === '#guided-tour-help') {
      document.getElementById('guided-tour-help')?.focus()
      window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search)
    }
  }, [loading, touring])

  return <>
    {loading && <div className="spa-loading" role="status">
      <span>Opening workspace…</span>
      <div className="workspace-loading-preview" aria-hidden="true">
        <span className="ui-skeleton skeleton-heading" />
        <div><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /></div>
        <span className="ui-skeleton skeleton-panel" />
      </div>
    </div>}
    {error && <main className="spa-error card" role="alert"><h1>Page unavailable</h1><p>{error}</p>
      <div className="btnrow"><button className="btn" onClick={() => { setError(''); navigate('/projects') }}>Go to projects</button>
        <a className="btn ghost" href="/legacy">Open the previous workspace</a></div></main>}
    <div hidden={Boolean(error)} inert={loading} className={touring ? 'guided-tour-workspace' : undefined}
      onClickCapture={event => {
        if (!touring) return
        event.preventDefault()
        event.stopPropagation()
      }}>
      <StableWorkspace />
    </div>
    {touring && <GuidedTourOverlay loading={loading || restoredPath !== location.pathname + location.search} error={Boolean(error)} />}
  </>
}
