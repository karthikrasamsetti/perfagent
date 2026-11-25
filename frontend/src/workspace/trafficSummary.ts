const header = 'window_start,window_seconds,method,route,requests'
export const maxTrafficBytes = 256 * 1024
const routePattern = /^\/(?!\/)[a-zA-Z0-9_./{}:\-~]*$/
const methods = new Set(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'])

export function summarizeTraffic(text: string) {
  const [columns, ...rows] = text.replace(/^\uFEFF/, '').trim().split(/\r?\n/)
  if (columns?.trim() !== header || rows.length === 0 || rows.length > 5000) {
    throw new Error('Use the example CSV format with 1–5,000 aggregate rows.')
  }

  const windows = new Map<number, { duration: number; count: number }>()
  const routes = new Map<string, number>()
  const seen = new Set<string>()
  let total = 0
  for (const [index, row] of rows.entries()) {
    const [start, seconds, method, route, requests, ...extra] = row.split(',').map(value => value.trim())
    const timestamp = Date.parse(start)
    const duration = Number(seconds)
    const count = Number(requests)
    if (extra.length || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(start) ||
        !Number.isFinite(timestamp) || new Date(timestamp).toISOString() !== start.replace(/Z$/, '.000Z') ||
        !/^\d+$/.test(seconds) || duration < 1 || duration > 86400 ||
        !methods.has(method) || !routePattern.test(route) || route.length > 200 ||
        !/^\d+$/.test(requests) || !Number.isSafeInteger(count) || count > 1e12) {
      throw new Error('Invalid aggregate traffic on CSV line ' + (index + 2) + '.')
    }
    const key = method + ' ' + route
    const unique = timestamp + ' ' + key
    const window = windows.get(timestamp) ?? { duration, count: 0 }
    if (seen.has(unique) || window.duration !== duration) {
      throw new Error('Use one row per route in each window with consistent window lengths.')
    }
    seen.add(unique)
    window.count += count
    windows.set(timestamp, window)
    routes.set(key, (routes.get(key) ?? 0) + count)
    total += count
  }

  let previousEnd = -Infinity
  let observedSeconds = 0
  let peakRate = 0
  for (const [start, window] of [...windows].sort(([a], [b]) => a - b)) {
    if (start < previousEnd) throw new Error('Traffic windows must not overlap.')
    previousEnd = start + window.duration * 1000
    observedSeconds += window.duration
    peakRate = Math.max(peakRate, window.count / window.duration)
  }
  if (!total) throw new Error('The sample must contain at least one request.')
  const mix = [...routes].sort(([, a], [, b]) => b - a)
    .map(([route, count]) => ({ route, count, share: count / total }))
  return { peakRate, meanRate: total / observedSeconds, windows: windows.size, mix }
}
