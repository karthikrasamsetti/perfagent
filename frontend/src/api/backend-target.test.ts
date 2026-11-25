import { describe, expect, it } from 'vitest'
import { backendTarget } from './backend-target'

describe('development API proxy', () => {
  it('targets PerfAgent on 8080, leaving 8000 for the sample target', () => {
    expect(backendTarget({})).toBe('http://127.0.0.1:8080')
    expect(backendTarget({ PERFAGENT_API_URL: ' ' })).toBe('http://127.0.0.1:8080')
  })
  it('accepts an explicit backend override', () => {
    expect(backendTarget({ PERFAGENT_API_URL: 'http://localhost:9000/' })).toBe('http://localhost:9000')
  })
  it('rejects credentials and non-HTTP targets', () => {
    expect(() => backendTarget({ PERFAGENT_API_URL: 'file:///private' })).toThrow('HTTP(S)')
    expect(() => backendTarget({ PERFAGENT_API_URL: 'http://user:secret@localhost:9000' })).toThrow('credentials')
  })
})
