export type WorkspaceRoute = {
  kind: 'projects' | 'project' | 'new-project' | 'settings' | 'new-test' | 'test' |
    'import-script' | 'import-git' | 'dashboard' | 'library' | 'report' | 'admin' |
    'monitoring' | 'activity' | 'not-found'
  projectId?: string
  testId?: string
  runId?: string
  step: number
  setup: boolean
}

export function resolveRoute(location: string): WorkspaceRoute {
  const url = new URL(location, 'http://perfagent.local')
  const path = url.pathname.replace(/\/$/, '') || '/'
  const rawStep = Number(url.searchParams.get('step') || 2)
  const base = { step: Math.max(1, Math.min(5, Number.isInteger(rawStep) ? rawStep : 2)), setup: url.searchParams.get('stage') === 'setup' }
  const staticRoutes: Record<string, WorkspaceRoute['kind']> = {
    '/': 'projects', '/projects': 'projects', '/projects/new': 'new-project',
    '/admin/overview': 'admin', '/monitoring': 'monitoring', '/activity': 'activity',
  }
  if (staticRoutes[path]) return { ...base, kind: staticRoutes[path] }
  const match = path.match(/^\/projects\/([a-zA-Z0-9_-]+)(?:\/(.*))?$/)
  if (!match) return { ...base, kind: 'not-found' }
  const projectId = match[1], tail = match[2] || ''
  const projectRoutes: Record<string, WorkspaceRoute['kind']> = {
    '': 'project', settings: 'settings', dashboard: 'dashboard', tests: 'library',
    'tests/new': 'new-test', 'import/script': 'import-script', 'import/git': 'import-git',
  }
  if (projectRoutes[tail]) return { ...base, projectId, kind: projectRoutes[tail] }
  const test = tail.match(/^tests\/([a-zA-Z0-9_-]+)$/)
  if (test) return { ...base, projectId, testId: test[1], kind: 'test' }
  const run = tail.match(/^runs\/([a-zA-Z0-9_-]+)$/)
  if (run) return { ...base, projectId, runId: run[1], kind: 'report' }
  return { ...base, kind: 'not-found' }
}
