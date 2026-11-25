import { useEffect, useRef, useState } from 'react'
import { requestJson } from '../api/client'
import type { components } from '../api/schema'
import { Icon } from './Icon'

const context = {
  demo: { label: 'Demo', title: 'Sample workspace', detail: 'Requests and reports use sample data.' },
  local: { label: 'Local', title: 'Local workspace', detail: 'This workspace is running in local mode.' },
  managed: { label: 'Managed', title: 'Organization workspace', detail: 'Access is verified by your organization’s MFA gateway.' },
  pending: { label: 'Workspace', title: 'Workspace session', detail: 'Checking workspace access…' },
  unavailable: { label: 'Workspace', title: 'Workspace session', detail: 'Session details are unavailable.' },
}

export function WorkspaceAccount() {
  const demo = document.documentElement.dataset.demo === 'true'
  const [mode, setMode] = useState<keyof typeof context>(demo ? 'demo' : 'pending')
  const summary = useRef<HTMLElement>(null)
  const session = context[mode]

  useEffect(() => {
    if (demo) return
    const controller = new AbortController()
    void requestJson<components['schemas']['WorkspaceSession']>('/api/workspace/session', { signal: controller.signal })
      .then(result => setMode(result.managed ? 'managed' : 'local'))
      .catch(() => { if (!controller.signal.aborted) setMode('unavailable') })
    return () => controller.abort()
  }, [demo])

  return (
    <details className="workspace-account" onBlur={event => {
      if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false
    }} onKeyDown={event => {
      if (event.key !== 'Escape' || !event.currentTarget.open) return
      event.preventDefault()
      event.currentTarget.open = false
      summary.current?.focus()
    }}>
      <summary className="btn ghost sm" ref={summary} aria-label={`Workspace account, ${session.label}`}>
        <Icon name="shield" /><span>{session.label}</span>
      </summary>
      <div className="workspace-account-panel">
        <strong>{session.title}</strong>
        <p role="status">{session.detail}</p>
        <div className="usage-chip" id="sessionUsage" hidden={mode !== 'local' && mode !== 'demo'}>
          <span>AI usage</span><strong id="sessionTokens">0</strong><span>tokens</span><span id="sessionCost" />
        </div>
        <a href={demo ? '/demo' : '/'}>{demo ? 'Restart demo' : 'PerfAgent home'}</a>
      </div>
    </details>
  )
}
