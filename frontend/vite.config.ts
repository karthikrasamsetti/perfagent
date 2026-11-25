import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { backendTarget } from './src/api/backend-target.ts'

export default defineConfig(({ mode }) => {
  const root = fileURLToPath(new URL('..', import.meta.url))
  const env = loadEnv(mode, root, 'PERFAGENT_API_URL')
  const target = backendTarget({ ...env, ...process.env })
  const demo = mode === 'demo'
  return {
  plugins: [react(), ...(demo ? [{
    name: 'perfagent-demo-policy',
    transformIndexHtml() {
      return [{ tag: 'meta', attrs: {
        'http-equiv': 'Content-Security-Policy',
        content: "default-src 'self'; connect-src 'none'; frame-src 'none'; object-src 'none'; form-action 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:",
      }, injectTo: 'head-prepend' as const }]
    },
  }] : [])],
  server: {
    strictPort: true,
    proxy: demo ? undefined : {
      '/api': { target, changeOrigin: false },
      '/legacy': { target, changeOrigin: false },
    },
  },
  ...(demo ? { preview: { proxy: {} } } : {}),
  build: {
    outDir: demo ? 'dist-demo' : '../src/perfagent/web/spa',
    emptyOutDir: true,
    sourcemap: false,
  },
  }
})
