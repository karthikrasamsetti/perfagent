import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, requestJson } from './client'

afterEach(() => vi.unstubAllGlobals())

describe('API client', () => {
  it('uses same-origin JSON requests and generated project input types', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ project_id: 'a', name: 'Commerce' })))
    vi.stubGlobal('fetch', fetch)
    await expect(api.projects.create({ name: 'Commerce' })).resolves.toMatchObject({ project_id: 'a' })
    expect(fetch.mock.calls[0][0]).toBe('/api/projects')
    expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'POST', credentials: 'same-origin' })
  })
  it('reports authorization failures without persisting credentials', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Administrator access required' }), { status: 403 })))
    await expect(requestJson('/api/admin/dashboard')).rejects.toMatchObject({ status: 403, message: 'Administrator access required' })
  })
  it('does not echo validation payloads that may contain secrets', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ input: 'private-token' }] }), { status: 422 })))
    await expect(requestJson('/api/projects')).rejects.toThrow('Check the form values')
  })
  it('handles unreadable responses and blocks external API destinations', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502 })))
    await expect(requestJson('/api/projects')).rejects.toBeInstanceOf(ApiError)
    await expect(requestJson('https://other.example/api/projects')).rejects.toThrow('application API')
  })
})
