import { describe, expect, it } from 'vitest'
import { summarizeTraffic } from './trafficSummary'

const csv = (...rows: string[]) => ['window_start,window_seconds,method,route,requests', ...rows].join('\n')

describe('aggregate traffic import', () => {
  it('computes peak across whole windows and the time-weighted mean', () => {
    const result = summarizeTraffic(csv(
      '2026-01-10T12:00:00Z,60,GET,/products,720',
      '2026-01-10T12:00:00Z,60,POST,/checkout,180',
      '2026-01-10T12:01:00Z,30,GET,/products,300',
    ))
    expect(result.peakRate).toBe(15)
    expect(result.meanRate).toBeCloseTo(13.3333)
    expect(result.windows).toBe(2)
    expect(result.mix[0]).toEqual({ route: 'GET /products', count: 1020, share: 0.85 })
  })

  it.each(['https://example.test/products', '//example.test', '/users?token=secret', '/<script>', '/name,field'])(
    'rejects non-template routes %s', route => {
      expect(() => summarizeTraffic(csv('2026-01-10T12:00:00Z,60,GET,' + route + ',100'))).toThrow()
    },
  )

  it('rejects duplicates and overlapping windows', () => {
    const row = '2026-01-10T12:00:00Z,60,GET,/products,100'
    expect(() => summarizeTraffic(csv(row, row))).toThrow('one row per route')
    expect(() => summarizeTraffic(csv(row, '2026-01-10T12:00:30Z,60,POST,/checkout,100'))).toThrow('overlap')
  })
})
