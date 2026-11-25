import { describe, expect, it } from 'vitest'
import { resolveRoute } from './routes'

describe('workspace routes', () => {
  it('opens Home at the root and keeps the project library addressable', () => {
    expect(resolveRoute('/').kind).toBe('home')
    expect(resolveRoute('/projects').kind).toBe('projects')
  })
  it('recognizes project-scoped screens and test steps', () => {
    expect(resolveRoute('/projects/commerce/dashboard')).toMatchObject({ kind: 'dashboard', projectId: 'commerce' })
    expect(resolveRoute('/projects/commerce/tests/checkout?step=3')).toMatchObject({ kind: 'test', testId: 'checkout', step: 3 })
    expect(resolveRoute('/projects/commerce/tests/new?stage=setup&step=1')).toMatchObject({ kind: 'new-test', setup: true, step: 1 })
    expect(resolveRoute('/projects/commerce/runs/run-a')).toMatchObject({ kind: 'report', runId: 'run-a' })
  })
  it('recognizes live bookmarks and limits them to the run step', () => {
    expect(resolveRoute('/projects/a/tests/b')).toMatchObject({ explicitStep: false })
    expect(resolveRoute('/projects/a/tests/b?step=4&run=abc-42')).toMatchObject({ explicitStep: true, liveRunId: 'abc-42' })
    expect(resolveRoute('/projects/a/tests/b?step=3&run=abc-42').liveRunId).toBeUndefined()
    expect(resolveRoute('/projects/a/tests/b?step=4&run=abc%2F42').liveRunId).toBeUndefined()
  })
  it('keeps imports separate from test creation', () => {
    expect(resolveRoute('/projects/a/import/script').kind).toBe('import-script')
    expect(resolveRoute('/projects/a/import/git').kind).toBe('import-git')
    expect(resolveRoute('/projects/new').kind).toBe('new-project')
    expect(resolveRoute('/admin/overview').kind).toBe('admin')
  })
  it('bounds test steps and rejects unknown routes', () => {
    expect(resolveRoute('/projects/a/tests/b?step=999').step).toBe(5)
    expect(resolveRoute('/projects/a/tests/b?step=nope').step).toBe(2)
    expect(resolveRoute('/projects/a/missing').kind).toBe('not-found')
    expect(resolveRoute('/not-a-real-page').kind).toBe('not-found')
  })
})
