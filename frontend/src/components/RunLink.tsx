import { useCallback, useState } from 'react'
import { useLocation } from 'react-router'
import { resolveRoute } from '../routing/routes'

export function RunLink({ kind }: { kind: 'live' | 'report' }) {
  const { pathname, search } = useLocation()
  const route = resolveRoute(pathname + search)
  const [feedback, setFeedback] = useState<{ url: string; copied: boolean }>()
  const selectFallback = useCallback((input: HTMLInputElement | null) => {
    if (input) {
      input.focus()
      input.select()
    }
  }, [])
  const runId = kind === 'live' ? route.liveRunId : route.runId || route.liveRunId
  if (document.documentElement.dataset.demo === 'true' || !route.projectId || !runId) return null

  const project = '/projects/' + encodeURIComponent(route.projectId)
  const path = kind === 'live' && route.testId
    ? project + '/tests/' + encodeURIComponent(route.testId) + '?step=4&run=' + encodeURIComponent(runId)
    : project + '/runs/' + encodeURIComponent(runId)
  const url = new URL(path, window.location.origin).href
  const result = feedback?.url === url ? feedback : undefined
  const label = kind === 'live' ? 'run' : 'report'

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setFeedback({ url, copied: true })
    } catch {
      setFeedback({ url, copied: false })
    }
  }

  return <div className="run-link">
    <button className="btn ghost sm" type="button" onClick={() => void copy()}>Copy {label} link</button>
    <span className="run-link-status" role="status">{result?.copied ? 'Link copied' : result ? 'Copy the link below.' : ''}</span>
    {result && !result.copied && <input ref={selectFallback} aria-label={kind === 'live' ? 'Live run URL' : 'Report URL'} readOnly value={url} />}
  </div>
}
