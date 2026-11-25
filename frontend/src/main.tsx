import { lazy, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, MemoryRouter, useLocation } from 'react-router'
import { App } from './App'
import { demoReportPath, demoTestPath } from './demo/fixtures'
import { tourStep } from './components/GuidedTour'
import '@fontsource-variable/geist'
import '@fontsource/ibm-plex-mono/latin-400.css'
import './styles/workspace.css'
import './styles/spa.css'

const PublicPage = lazy(async () => {
  const { LandingPage } = await import('./pages/LandingPage')
  return { default: LandingPage }
})

function BrowserShell() {
  const { pathname } = useLocation()
  const path = pathname.replace(/\/$/, '')
  const page = path === '/sign-in' ? 'sign-in' : path === '/sign-up' ? 'sign-up' : !path ? 'landing' : null
  if (!page || (!path && import.meta.env.MODE === 'demo')) return <App />
  const accessMode = document.querySelector<HTMLMetaElement>('meta[name="perfagent-access-mode"]')?.content
  return <Suspense fallback={<div className="spa-loading" role="status">Opening PerfAgent…</div>}>
    <PublicPage page={page} loginHandoff={accessMode !== 'local'} />
  </Suspense>
}

async function mount() {
  const root = createRoot(document.getElementById('root')!)
  const pathname = window.location.pathname.replace(/\/$/, '')
  const sample = pathname === '/demo'
  const tour = sample && tourStep(window.location.search) >= 0
  if (sample || import.meta.env.MODE === 'demo') {
    const { createDemoBackend } = await import('./demo/backend')
    window.fetch = createDemoBackend()
    document.documentElement.dataset.demo = 'true'
    if (tour) document.documentElement.dataset.tour = 'true'
  }
  if (sample) {
    const view = new URLSearchParams(window.location.search).get('view')
    const entry = tour ? '/workspace' + window.location.search
      : view === 'review' ? demoTestPath + '?step=2'
        : view === 'verify' ? demoTestPath + '?step=3'
          : view === 'report' ? demoReportPath : '/workspace'
    root.render(<MemoryRouter initialEntries={[entry]}><App /></MemoryRouter>)
  } else root.render(<BrowserRouter><BrowserShell /></BrowserRouter>)
}

void mount()
