import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { demoProjectPath, demoReportPath, demoTestPath } from '../demo/fixtures'

const preferenceKey = 'perfagent:guided-tour:v2'
const stops = [
  { title: 'Home', path: '/workspace', target: '.home-lead .btnrow', detail: 'Start with the example checkout test, open the sample project, or jump to its release report.' },
  { title: 'Projects', path: '/projects', target: '#view-projects .projects-intro', detail: 'Open a project to find its tests, saved runs, and dashboard.' },
  { title: 'Describe', path: demoTestPath + '?step=1', target: '#target', detail: 'Enter the target URL here, then add requests and choose how to schedule traffic. You can set a user count or throughput goal.' },
  { title: 'Review plan', path: demoTestPath + '?step=2', target: '#reviewRequestsTitle', detail: 'Review the drafted requests, add response checks, attach data, or capture a value for a later request. Preview sample requests before you approve.' },
  { title: 'Verify', path: demoTestPath + '?step=3', target: '#verifyTrafficHeading', detail: 'Inspect the k6 script and verify the requests and checks. Use Release or commit to label a candidate for comparison.' },
  { title: 'Run', path: demoTestPath + '?step=4', target: '#panel4 .live-run-header h2', detail: 'This is where live measurements appear after you start a run from Verify. Watch throughput, errors, and latency here.' },
  { title: 'Report', path: demoReportPath, target: '#releaseReadinessTitle', detail: 'Compare the candidate with its baseline and check the release verdict. Scroll farther down for k6 thresholds, timelines, and endpoint results.' },
  { title: 'Dashboard', path: demoProjectPath + '/dashboard', target: '.dashboard-heading h2', detail: 'Filter historical runs by test or environment. Inspect trends and open individual reports for evidence.' },
]

export function tourStep(search: string) {
  const value = new URLSearchParams(search).get('tour')
  return value !== null && /^[0-7]$/.test(value) ? Number(value) : -1
}

function tourPath(step: number, returnTo: string) {
  const url = new URL(stops[step].path, window.location.origin)
  url.searchParams.set('tour', String(step))
  url.searchParams.set('return', returnTo)
  return url.pathname + url.search
}

function markSeen() {
  try { localStorage.setItem(preferenceKey, 'seen') } catch { /* Storage is optional. */ }
}

export function GuidedTour() {
  const dialog = useRef<HTMLDialogElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)

  function open() {
    dialog.current?.showModal()
    heading.current?.focus()
  }

  useEffect(() => {
    try {
      if (!localStorage.getItem(preferenceKey)) open()
    } catch { /* Help remains available without storage. */ }
  }, [])

  return <>
    <button id="guided-tour-help" className="btn ghost sm" type="button" ref={trigger} onClick={open}
      aria-haspopup="dialog">Help<span className="tour-help-label"> · Guided tour</span></button>
    <dialog ref={dialog} className="guided-tour" aria-labelledby="tour-title" onClose={() => {
      markSeen()
      trigger.current?.focus()
    }}>
      <div className="guided-tour-content">
        <h2 id="tour-title" ref={heading} tabIndex={-1}>Take a tour of PerfAgent</h2>
        <p>We’ll open each page and highlight where to look. The tour uses a sample checkout project and sends no test traffic.</p>
        <div className="guided-tour-actions">
          <button type="button" className="btn ghost sm" onClick={() => dialog.current?.close()}>Skip tour</button>
          <button type="button" className="btn sm" onClick={() => {
            markSeen()
            const start = new URL(tourPath(0, window.location.pathname + window.location.search), window.location.origin)
            window.location.assign('/demo' + start.search)
          }}>Start tour</button>
        </div>
      </div>
    </dialog>
  </>
}

export function GuidedTourOverlay({ loading, error }: { loading: boolean; error: boolean }) {
  const location = useLocation()
  const navigate = useNavigate()
  const heading = useRef<HTMLHeadingElement>(null)
  const actions = useRef<HTMLDivElement>(null)
  const card = useRef<HTMLElement>(null)
  const step = tourStep(location.search)
  const stop = stops[step]
  const returnTo = new URLSearchParams(location.search).get('return') || '/'
  const lastStep = step === stops.length - 1

  useEffect(() => {
    if (!stop || loading || error) return
    const target = document.querySelector<HTMLElement>(stop.target)
    const overlay = card.current
    if (!target || !overlay) {
      heading.current?.focus()
      return
    }

    const tabIndex = target.getAttribute('tabindex')
    const description = target.getAttribute('aria-describedby')
    const readOnly = target instanceof HTMLInputElement ? target.readOnly : undefined
    if (target instanceof HTMLInputElement) target.readOnly = true
    target.tabIndex = -1
    target.setAttribute('aria-describedby', ['tour-title', 'tour-detail', description].filter(Boolean).join(' '))
    target.classList.add('guided-tour-highlight')
    let active = true
    function positionCard() {
      if (!active || !target || !overlay) return
      const anchor = target.getBoundingClientRect()
      const edge = 12
      const gap = 14
      const right = document.documentElement.clientWidth - edge
      const bottom = window.innerHeight - edge
      const width = overlay.offsetWidth
      const height = overlay.querySelector('.guided-tour-content')!.scrollHeight + 2
      const clip = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value))
      const left = clip(anchor.left, edge, right - width)
      const belowTop = Math.max(edge, anchor.bottom + gap)
      const aboveBottom = Math.min(bottom, anchor.top - gap)
      const above = { left, top: Math.max(edge, aboveBottom - height), space: Math.max(0, aboveBottom - edge) }
      const below = { left, top: Math.min(bottom, belowTop), space: Math.max(0, bottom - belowTop) }
      const choices = [below, above]
      const sideTop = clip(anchor.top, edge, bottom - height)

      if (anchor.right + gap + width <= right) {
        choices.push({ left: Math.max(edge, anchor.right + gap), top: sideTop, space: bottom - sideTop })
      }
      if (anchor.left - gap - width >= edge) {
        choices.push({ left: Math.min(right - width, anchor.left - gap - width), top: sideTop, space: bottom - sideTop })
      }

      const position = choices.find(choice => choice.space >= height)
        ?? choices.reduce((best, choice) => choice.space > best.space ? choice : best)
      overlay.dataset.anchored = 'true'
      overlay.style.setProperty('--tour-left', position.left + 'px')
      overlay.style.setProperty('--tour-top', position.top + 'px')
      overlay.style.setProperty('--tour-space', Math.max(0, position.space) + 'px')
    }

    function revealTarget() {
      target?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' })
      positionCard()
    }

    const frame = requestAnimationFrame(() => {
      revealTarget()
      target.focus({ preventScroll: true })
    })
    const observer = new ResizeObserver(positionCard)
    const content = overlay.querySelector('.guided-tour-content')
    if (content) observer.observe(content)
    observer.observe(target)
    if (target.parentElement) observer.observe(target.parentElement)
    const workspace = document.getElementById('workspace-content')
    if (workspace) observer.observe(workspace)
    void document.fonts.ready.then(positionCard)
    window.addEventListener('resize', revealTarget)
    window.addEventListener('scroll', positionCard, true)

    function moveToTourControls(event: KeyboardEvent) {
      if (event.key !== 'Tab') return
      event.preventDefault()
      const buttons = actions.current?.querySelectorAll<HTMLButtonElement>('button:enabled')
      if (buttons?.length) buttons[event.shiftKey ? buttons.length - 1 : 0].focus()
    }

    target.addEventListener('keydown', moveToTourControls)
    return () => {
      active = false
      cancelAnimationFrame(frame)
      observer.disconnect()
      window.removeEventListener('resize', revealTarget)
      window.removeEventListener('scroll', positionCard, true)
      delete overlay.dataset.anchored
      overlay.style.removeProperty('--tour-left')
      overlay.style.removeProperty('--tour-top')
      overlay.style.removeProperty('--tour-space')
      target.removeEventListener('keydown', moveToTourControls)
      target.classList.remove('guided-tour-highlight')
      if (tabIndex === null) target.removeAttribute('tabindex')
      else target.setAttribute('tabindex', tabIndex)
      if (description === null) target.removeAttribute('aria-describedby')
      else target.setAttribute('aria-describedby', description)
      if (target instanceof HTMLInputElement && readOnly !== undefined) target.readOnly = readOnly
    }
  }, [stop, loading, error])

  function finish() {
    markSeen()
    const destination = new URL(returnTo.startsWith('/') ? returnTo : '/', window.location.origin)
    if (destination.origin !== window.location.origin || destination.searchParams.has('tour')) {
      window.location.replace('/')
      return
    }
    destination.hash = 'guided-tour-help'
    window.location.replace(destination.href)
  }

  if (!stop) return null
  return <aside ref={card} className="guided-tour guided-tour-overlay" aria-labelledby="tour-title"
    onKeyDown={event => { if (event.key === 'Escape') finish() }}>
    <div className="guided-tour-content">
      <h2 id="tour-title" ref={heading} tabIndex={-1}><span>Step {step + 1} of {stops.length}</span>{stop.title}</h2>
      <p id="tour-detail">{error ? 'This sample page could not be opened. You can continue or exit the tour.' : stop.detail}</p>
      <div className="guided-tour-actions" ref={actions} onKeyDown={event => {
        if (event.key !== 'Tab') return
        const buttons = actions.current?.querySelectorAll<HTMLButtonElement>('button:enabled')
        if (!buttons?.length) return
        if (event.target !== buttons[event.shiftKey ? 0 : buttons.length - 1]) return
        const target = document.querySelector<HTMLElement>(stop.target)
        if (!target) return
        event.preventDefault()
        target.focus({ preventScroll: true })
      }}>
        <button type="button" className="btn ghost sm" onClick={finish}>Skip tour</button>
        <button type="button" className="btn ghost sm" disabled={step === 0 || loading}
          onClick={() => navigate(tourPath(step - 1, returnTo), { replace: true })}>Previous</button>
        <button type="button" className="btn sm" disabled={loading} onClick={() => {
          if (lastStep) finish()
          else navigate(tourPath(step + 1, returnTo), { replace: true })
        }}>{lastStep ? 'Done' : 'Next'}</button>
      </div>
    </div>
  </aside>
}
