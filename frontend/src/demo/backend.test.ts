import { expect, it } from 'vitest'
import { createDemoBackend } from './backend'

const origin = 'http://localhost:4174'

it('serves the seeded blocked release and denies external or unsupported operations', async () => {
  const demo = createDemoBackend(origin)
  const report = await (await demo('/api/runs/demo-candidate/saved-report')).json()
  expect(report.release_readiness.status).toBe('blocked')
  expect(report.verdict.overall_passed).toBe(true)
  expect((await demo('https://elsewhere.test/api/projects')).status).toBe(403)
  expect((await demo('/api/jenkins/trigger', { method: 'POST' })).status).toBe(403)
})

it('simulates a completed run and keeps it out of a new demo session', async () => {
  let time = 0
  const demo = createDemoBackend(origin, () => time)
  const started = await (await demo('/api/scripts/checkout-script/run', {
    method: 'POST', body: JSON.stringify({ release_label: 'Demo run' }),
  })).json()
  const endpoint = '/api/runs/' + started.run_id
  expect((await (await demo(endpoint)).json()).status).toBe('running')
  time = 6001
  expect((await (await demo(endpoint)).json()).status).toBe('finished')
  const report = await (await demo(endpoint + '/report')).json()
  expect(report.execution.release_label).toBe('Demo run')
  expect((await createDemoBackend(origin)(endpoint + '/report')).status).toBe(403)
})
