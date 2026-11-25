import type { components } from './schema'

export type ProjectInput = components['schemas']['ProjectBody']
export type Project = ProjectInput & { project_id: string; created_at?: string; tests?: number }
export type PlanInput = components['schemas']['PlanRequest']
export type WorkloadInput = components['schemas']['WorkloadBody']
export type RunInput = components['schemas']['RunOptions']

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = 'ApiError' }
}

export async function requestJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  if (!url.startsWith('/api/')) throw new Error('API requests must use the application API.')
  const response = await fetch(url, { ...options, credentials: 'same-origin' })
  let data: unknown
  try { data = await response.json() }
  catch { throw new ApiError(response.status, 'The server returned an unreadable response. Please retry.') }
  if (!response.ok) {
    const detail = (data as { detail?: unknown })?.detail
    throw new ApiError(response.status, typeof detail === 'string' ? detail : 'The request failed. Check the form values and retry.')
  }
  return data as T
}

const json = (body: unknown): RequestInit => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export const api = {
  projects: {
    list: (signal?: AbortSignal) => requestJson<{ projects: Project[] }>('/api/projects', { signal }),
    create: (body: ProjectInput) => requestJson<Project>('/api/projects', { ...json(body), method: 'POST' }),
    update: (id: string, body: ProjectInput) => requestJson<Project>(`/api/projects/${encodeURIComponent(id)}`, { ...json(body), method: 'PUT' }),
  },
  plan: (body: PlanInput) => requestJson('/api/plan', { ...json(body), method: 'POST' }),
  saveWorkload: (id: string, body: WorkloadInput) => requestJson(`/api/plans/${encodeURIComponent(id)}/workloads`, { ...json(body), method: 'POST' }),
  run: (id: string, body: RunInput) => requestJson(`/api/scripts/${encodeURIComponent(id)}/run`, { ...json(body), method: 'POST' }),
}
