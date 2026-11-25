import { createRoot } from 'react-dom/client'
import { BrowserRouter, MemoryRouter } from 'react-router'
import { App } from './App'
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
  if (!tour && !sample && (!pathname || pathname === '/sign-in') && import.meta.env.MODE !== 'demo') {
    const { LandingPage } = await import('./pages/LandingPage')
    root.render(<LandingPage access={pathname === '/sign-in'} />)
    return
  }
  if (tour || sample || import.meta.env.MODE === 'demo') {
    const { createDemoBackend } = await import('./demo/backend')
    window.fetch = createDemoBackend()
    document.documentElement.dataset.demo = 'true'
    if (tour) document.documentElement.dataset.tour = 'true'
  }
  if (sample) root.render(<MemoryRouter initialEntries={['/workspace' + window.location.search]}><App /></MemoryRouter>)
  else root.render(<BrowserRouter><App /></BrowserRouter>)
}

void mount()
