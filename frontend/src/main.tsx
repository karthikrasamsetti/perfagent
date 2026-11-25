import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { App } from './App'
import { tourStep } from './components/GuidedTour'
import '@fontsource-variable/geist'
import '@fontsource/ibm-plex-mono/latin-400.css'
import './styles/workspace.css'
import './styles/spa.css'

async function mount() {
  const tour = tourStep(window.location.search) >= 0
  if (tour || import.meta.env.MODE === 'demo') {
    const { createDemoBackend } = await import('./demo/backend')
    window.fetch = createDemoBackend()
    document.documentElement.dataset.demo = 'true'
    if (tour) document.documentElement.dataset.tour = 'true'
  }
  createRoot(document.getElementById('root')!).render(<BrowserRouter><App /></BrowserRouter>)
}

void mount()
