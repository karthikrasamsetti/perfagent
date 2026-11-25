// This config helper is imported by Vite, never by the browser entry point.
export const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8080'

export function backendTarget(env: Record<string, string | undefined>): string {
  const value = env.PERFAGENT_API_URL?.trim() || DEFAULT_BACKEND_URL
  const url = new URL(value)
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
    throw new Error('PERFAGENT_API_URL must be an HTTP(S) backend URL without credentials.')
  }
  return value.replace(/\/$/, '')
}
