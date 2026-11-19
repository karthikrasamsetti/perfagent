import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { App } from './App'
import './styles/workspace.css'
import './styles/spa.css'

createRoot(document.getElementById('root')!).render(<BrowserRouter><App /></BrowserRouter>)
