import { createServer as createHttpServer } from 'node:http'
import type { AddressInfo } from 'node:net'
import { createServer } from 'vite'
import { expect, it, vi } from 'vitest'
import config from '../../vite.config.ts'

it('forwards a project POST through the real Vite proxy with its body intact', async () => {
  let received: { method?: string; url?: string; host?: string; origin?: string; body: string } | undefined
  const backend = createHttpServer(async (request, response) => {
    let body = ''
    for await (const chunk of request) body += chunk
    received = { method: request.method, url: request.url, host: request.headers.host, origin: request.headers.origin, body }
    response.writeHead(201, { 'Content-Type': 'application/json' })
    response.end(JSON.stringify({ project_id: 'proxy-check' }))
  })
  await new Promise<void>(resolve => backend.listen(0, '127.0.0.1', resolve))
  vi.stubEnv('PERFAGENT_API_URL', `http://127.0.0.1:${(backend.address() as AddressInfo).port}`)
  let frontend: Awaited<ReturnType<typeof createServer>> | undefined
  try {
    const configured = await config({ mode: 'test', command: 'serve' })
    frontend = await createServer({ ...configured, configFile: false, logLevel: 'silent', server: {
      ...configured.server, host: '127.0.0.1', port: 0, strictPort: false,
    } })
    await frontend.listen()
    const address = frontend.httpServer!.address() as AddressInfo
    const host = `127.0.0.1:${address.port}`
    const origin = `http://${host}`
    const response = await fetch(`${origin}/api/projects`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Origin: origin }, body: JSON.stringify({ name: 'Proxy check' }),
    })
    expect(response.status).toBe(201)
    expect(await response.json()).toEqual({ project_id: 'proxy-check' })
    expect(received).toEqual({ method: 'POST', url: '/api/projects', host, origin, body: '{"name":"Proxy check"}' })
  } finally {
    if (frontend?.httpServer && 'closeAllConnections' in frontend.httpServer) frontend.httpServer.closeAllConnections()
    await frontend?.close()
    backend.closeAllConnections()
    await new Promise<void>(resolve => backend.close(() => resolve()))
    vi.unstubAllEnvs()
  }
}, 15000)
