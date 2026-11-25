type Step = { name?: string; method: string; path: string; assertions?: unknown[]; body?: unknown }
type Model = {
  test_name: string; script_filename?: string; target_base_url: string; environment: string
  scenarios: { name: string; weight: number; steps: Step[]; think_time: { min_seconds: number; max_seconds: number } }[]
  load_profile: { stages: { duration_seconds: number; target_users: number }[]; arrival_rate?: number; target_request_rate?: number; pre_allocated_vus?: number }
  thresholds: { metric: string; op: string; value: number }[]
}
const target = 'https://checkout.demo.test'
const project = {
  project_id: 'commerce-demo', name: 'Commerce Demo', framework_name: 'commerce',
  description: 'Example workloads and releases for a storefront checkout.',
  target_url: target, environment: 'staging', branch: 'main', ci: [],
}
const script = {
  script_id: 'checkout-script', tool: 'k6', filename: 'checkout.js', source: 'generated',
  created_at: '2026-11-24T09:00:00Z',
}
const sampleScript = '// Simulated PerfAgent script preview.\nexport default function () {}\n'
const initial: Model = {
  test_name: 'Checkout API', script_filename: 'checkout.js', target_base_url: target, environment: 'staging',
  scenarios: [{ name: 'Checkout', weight: 1, think_time: { min_seconds: 1, max_seconds: 2 },
    steps: [{ name: 'Submit checkout', method: 'POST', path: '/checkout', body: {},
      assertions: [{ kind: 'json_path', op: 'exists', path: 'order_id' }] }] }],
  load_profile: { stages: [{ duration_seconds: 30, target_users: 5 }], arrival_rate: 15, target_request_rate: 15, pre_allocated_vus: 5 },
  thresholds: [{ metric: 'p95_ms', op: '<=', value: 300 }, { metric: 'error_rate', op: '<', value: .01 }],
}
const baselineId = 'demo-baseline'
const candidateId = 'demo-candidate'
const policy = { max_p95_ms: 300, max_error_percent: 1, max_p95_regression_percent: 10 }

function measurements(p95: number, rps: number, requests: number) {
  return { requests, error_rate: 0, rps, active_vus: 5, dropped_iterations: 0,
    iterations: requests, iterations_per_second: rps,
    latency: { samples: requests, avg_ms: p95 * .6, p50_ms: p95 * .55, p95_ms: p95, p99_ms: p95 * 1.15 },
    per_endpoint: [{ name: 'Submit checkout', requests, failed: 0, avg_ms: p95 * .6, p95_ms: p95,
      checks_failed: 0, status_codes: { 200: requests } }],
    checks: [{ name: 'order_id exists', passed: requests, total: requests, failed: 0 }],
  }
}

function samples(p95: number) {
  return Array.from({ length: 10 }, (_, index) => ({
    t: (index + 1) * 3, p95: Math.round(p95 * (.76 + index * .026)),
    rps: index < 2 ? (index + 1) * 5 : 15, err: 0, dropped_iterations: 0,
  }))
}

function escapeHtml(value: string) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;')
}

function makeReport(id: string, planId: string, scriptId: string, model: Model, label: string, p95: number, stopped = false) {
  const profile = model.load_profile
  return {
    run_id: id, plan_id: planId, project_id: project.project_id, script_id: scriptId, target,
    status: stopped ? 'stopped' : 'finished', tool: 'k6', snapshot: measurements(p95, 15, 450), samples: samples(p95),
    execution: { test_name: model.test_name, script_name: script.filename, endpoint_summary: 'POST /checkout',
      environment: 'staging', release_label: label, mode: 'full', workload_version: 'demo-v1',
      target_request_rate: profile.target_request_rate, planned_phases: [{ label: 'Steady state', start_s: 0, end_s: 30 }] },
    verdict: { overall_passed: stopped ? null : true, checks: [
      { metric: 'p95_ms', op: '<=', actual: p95, target: 300, passed: true },
      { metric: 'error_rate', op: '<', actual: 0, target: .01, passed: true },
    ] },
    narrative: { headline: 'Simulated checkout workload', summary: 'The demo run completed at 15 requests per second.',
      observations: ['The fixture recorded no request failures.'], recommendations: [] },
    logs: ['Demo metrics generated in this browser.'],
  }
}

type Report = ReturnType<typeof makeReport>

export function createDemoBackend(origin = location.origin, now = Date.now) {
  const plans = new Map([['checkout-plan', structuredClone(initial)]])
  const scripts = new Map([[script.script_id, 'checkout-plan']])
  const reports = new Map<string, Report>([
    [baselineId, makeReport(baselineId, 'checkout-plan', script.script_id, initial, 'v2.3', 184)],
    [candidateId, makeReport(candidateId, 'checkout-plan', script.script_id, initial, 'v2.4', 222)],
  ])
  const live = new Map<string, { started: number; label: string; scriptId: string; stopped: boolean }>()
  const verification = new Set<string>()
  let revision = 0

  function readiness(report: Report) {
    const before = 184, current = report.snapshot.latency.p95_ms
    const self = report.run_id === baselineId
    const comparable = report.plan_id === 'checkout-plan' && !self && report.status === 'finished'
    if (report.plan_id !== 'checkout-plan') {
      return { status: 'needs_evidence', reason: 'The example baseline belongs to Checkout API.', environment: 'staging' }
    }
    const delta = ((current - before) / before) * 100
    const status = comparable ? (delta > 10 ? 'blocked' : 'ready') : 'needs_evidence'
    const reason = self ? 'This run is the approved baseline.' : status === 'blocked'
      ? 'p95 change from baseline breached its release budget.'
      : status === 'ready' ? 'All configured release budgets were met.' : 'A complete candidate run is required.'
    return {
      status, reason, environment: 'staging', baseline_id: baselineId, baseline_release: 'v2.3',
      candidate_id: report.run_id, candidate_release: report.execution.release_label,
      candidate_rps: 15, target_rps: 15, budgets: policy,
      explanation: 'The k6 measurements and release decision on this page are simulated. ' + reason,
      summary: `Checkout p95 was ${current} ms. The approved baseline was ${before} ms.`,
      rules: [{ name: 'p95 latency', op: '≤', limit: 300, unit: 'ms', actual: current, passed: true },
        { name: 'p95 change from baseline', op: '≤', limit: 10, unit: '%', actual: comparable ? delta : null,
          passed: comparable ? delta <= 10 : null }],
      ...(comparable ? { comparison: {
        baseline: samples(before), candidate: report.samples, phases: report.execution.planned_phases,
        baseline_metrics: { p95_ms: before, rps: 15, error_percent: 0 },
        candidate_metrics: { p95_ms: current, rps: 15, error_percent: 0 },
        endpoints: [{ name: 'Submit checkout', baseline_ms: before, candidate_ms: current }],
      } } : {}),
    }
  }

  function history() {
    return [...reports.values()].reverse().map((item, index) => ({
      ...item.execution, t: new Date(Date.UTC(2026, 10, 25, 9, -index * 30)).toISOString(),
      created_at: new Date(Date.UTC(2026, 10, 25, 9, -index * 30)).toISOString(),
      run_id: item.run_id, plan_id: item.plan_id, project_id: project.project_id,
      series_group: item.plan_id, target, verdict: item.status === 'finished' ? 'pass' : 'inconclusive',
      p50_ms: item.snapshot.latency.p50_ms, p95_ms: item.snapshot.latency.p95_ms,
      p99_ms: item.snapshot.latency.p99_ms, rps: 15, target_rps: 15,
      error_rate: 0, requests: 450, has_report: true, p95_limit: 300,
    }))
  }

  function reportFor(id: string): Report | undefined {
    const known = reports.get(id)
    if (known) return known
    const active = live.get(id)
    if (!active || (!active.stopped && now() - active.started < 6000)) return
    const planId = scripts.get(active.scriptId)!
    const report = makeReport(id, planId, active.scriptId, plans.get(planId)!, active.label, 222, active.stopped)
    reports.set(id, report)
    return report
  }

  function json(data: unknown, status = 200) {
    return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
  }

  return async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(new URL(input, origin), init)
    const url = new URL(request.url)
    if (url.origin !== origin || !url.pathname.startsWith('/api/')) {
      return json({ detail: 'This demo uses simulated operations only.' }, 403)
    }
    const path = url.pathname, method = request.method
    if (path === '/api/projects' && method === 'GET') return json({ projects: [{ ...project, tests: plans.size }] })
    if (path === '/api/tools') return json({ tools: ['k6'] })
    if (path === '/api/chat/config') return json({ enabled: false })
    if (path === '/api/run/available') return json({ k6: true })
    if (path === '/api/usage/total') return json({ total_tokens: 0, total_cost_usd: 0 })
    if (path === '/api/sla') return json({ profiles: [] })
    if (path === '/api/traces') return json({ traces: [] })
    if (path === '/api/audit') return json({ events: [] })
    if (path.endsWith('/dashboard') && method === 'GET') return json({ project, summary: {
      tests: plans.size, runs: reports.size, requests: reports.size * 450, pass_rate: 100,
    } })
    if (path === '/api/plans') return json({ plans: [...plans].map(([plan_id, model]) => ({
      plan_id, project_id: project.project_id, test_name: model.test_name, target, script_count: 1,
    })) })
    const planMatch = path.match(/^\/api\/plans\/([^/]+)$/)
    if (planMatch && plans.has(planMatch[1])) {
      const planId = planMatch[1]
      return json({ plan_id: planId, project_id: project.project_id, load_model: plans.get(planId),
        scripts: [...scripts].filter(([, id]) => id === planId).map(([script_id]) => ({ ...script, script_id })) })
    }
    if (path.endsWith('/workloads') && method === 'GET') return json({ workloads: [] })
    if (path === '/api/plan' && method === 'POST') {
      const form = await request.json()
      const planId = 'demo-plan-' + ++revision
      const model = structuredClone(initial)
      model.test_name = String(form.test_name || 'Example workload').slice(0, 120)
      model.scenarios[0].steps = Array.isArray(form.endpoints) && form.endpoints.length ? form.endpoints : initial.scenarios[0].steps
      plans.set(planId, model)
      return json({ plan_id: planId, load_model: model, provider: 'demo fixture',
        rationale: 'A steady checkout workload illustrates the planning and verification flow.' })
    }
    const generate = path.match(/^\/api\/plan\/([^/]+)\/generate$/)
    if (generate && method === 'POST' && plans.has(generate[1])) {
      const form = await request.json()
      const id = 'demo-script-' + ++revision
      plans.set(generate[1], { ...form.load_model, target_base_url: target })
      scripts.set(id, generate[1])
      return json({ ...script, script_id: id, content: sampleScript })
    }
    if (path === '/api/request-preview') {
      const form = await request.json()
      return json({ steps: (form.load_model?.scenarios || initial.scenarios).flatMap(
        (journey: Model['scenarios'][number]) => journey.steps.map(step => ({
          method: step.method, path: step.path, scenario: journey.name, url: target + step.path,
          body: step.body, undefined: [],
        })),
      ) })
    }
    const scriptMatch = path.match(/^\/api\/scripts\/([^/]+)\/(download|readiness|validate|run)$/)
    if (scriptMatch && scripts.has(scriptMatch[1])) {
      const [, id, action] = scriptMatch
      if (action === 'download') return new Response(sampleScript, { headers: { 'Content-Type': 'text/javascript' } })
      if (action === 'validate') return json({ ok: true, message: 'Simulated syntax validation passed.' })
      if (action === 'readiness') return json({ checks: [{ name: 'Demo', ok: true, detail: 'Simulation ready' }],
        execution: { duration_seconds: 30, peak_users: 5 },
        verification: verification.has(id) ? { all_ok: true, journeys_checked: 1, verified_at: now() / 1000 } : null,
      })
      if (action === 'run' && method === 'POST') {
        const form = await request.json()
        const run_id = 'demo-run-' + ++revision
        live.set(run_id, { started: now(), label: String(form.release_label || 'Simulated run').slice(0, 100), scriptId: id, stopped: false })
        return json({ run_id, status: 'running' })
      }
    }
    if (path === '/api/preflight' && method === 'POST') {
      const form = await request.json()
      verification.add(form.script_id)
      return json({ all_ok: true, ok: 1, total: 1, results: [{ method: 'POST', path: '/checkout', status: 200, ok: true }] })
    }
    if (path === '/api/runs' || path === '/api/reporting/runs' || path === '/api/runs/trend') {
      const entries = history().filter(run => !url.searchParams.get('plan_id') || run.plan_id === url.searchParams.get('plan_id'))
        .filter(run => !url.searchParams.get('release_label') || run.release_label === url.searchParams.get('release_label'))
      const latest = entries[0], report = latest && reports.get(latest.run_id)
      return json({ runs: entries, total: entries.length, points: entries.map(run => ({ ...run, value: run.p95_ms })),
        overview: { total: entries.length, passed: entries.filter(run => run.verdict === 'pass').length,
          failed: 0, inconclusive: entries.filter(run => run.verdict === 'inconclusive').length,
          requests: entries.reduce((sum, item) => sum + item.requests, 0),
          worst_p95_ms: entries.length ? Math.max(...entries.map(run => run.p95_ms)) : null, latest,
          release_readiness: report ? readiness(report) : null, trend: [...entries].reverse(), outcomes: [],
        } })
    }
    const runMatch = path.match(/^\/api\/runs\/([^/]+)(?:\/(.+))?$/)
    if (runMatch) {
      const [, id, action] = runMatch
      const active = live.get(id)
      if (action === 'stop' && active && method === 'POST') {
        active.stopped = true
        reportFor(id)
        return json({ status: 'stopped' })
      }
      const report = reportFor(id)
      if (!action && active) {
        const elapsed_s = Math.max(0, Math.min(30, (now() - active.started) / 200))
        return json({ status: report?.status || 'running', target, mode: 'full', elapsed_s,
          planned_load: { duration_seconds: 30, peak_users: 5, requests_per_second: 15 },
          snapshot: measurements(222, elapsed_s < 4 ? 8 : 15, Math.floor(elapsed_s * 15)),
          logs: ['Simulating a checkout workload.'],
        })
      }
      if (report && (action === 'report' || action === 'saved-report')) return json({ ...report, release_readiness: readiness(report) })
      if (report && action === 'report/download') {
        const decision = readiness(report)
        return new Response('<!doctype html><meta charset="utf-8"><title>PerfAgent demo report</title>' +
          '<h1>Simulated performance report</h1><p>' + escapeHtml(report.execution.release_label) + '</p><p>' +
          escapeHtml(decision.status + ' · ' + decision.reason) + '</p>', { headers: { 'Content-Type': 'text/html' } })
      }
      if (report && action === 'logs/download') return new Response(report.logs.join('\n'))
    }
    return json({ detail: 'This action is unavailable in the demo preview.' }, 403)
  }
}
