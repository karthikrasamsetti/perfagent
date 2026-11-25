import { createRoot } from 'react-dom/client'
import { BrowserRouter, MemoryRouter } from 'react-router'
import { App } from './App'
import { demoReportPath, demoTestPath } from './demo/fixtures'
import { tourStep } from './components/GuidedTour'
import '@fontsource-variable/geist'
import '@fontsource/ibm-plex-mono/latin-400.css'
import './styles/workspace.css'
import './styles/spa.css'

async function mount() {
  const root = createRoot(document.getElementById('root')!)
  const pathname = window.location.pathname.replace(/\/$/, '')
  const tour = tourStep(window.location.search) >= 0
  const sample = pathname === '/demo'
  const publicPage = pathname === '/sign-in' ? 'sign-in' : pathname === '/sign-up' ? 'sign-up' : 'landing'
  if (!tour && (!pathname || publicPage !== 'landing') && (import.meta.env.MODE !== 'demo' || pathname)) {
    const { LandingPage } = await import('./pages/LandingPage')
    root.render(<LandingPage page={publicPage} />)
    return
  }
  if (tour || sample || import.meta.env.MODE === 'demo') {
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
  } else root.render(<BrowserRouter><App /></BrowserRouter>)
}

void mount()
