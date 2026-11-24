import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { backendTarget } from './src/api/backend-target.ts'

export default defineConfig(({ mode }) => {
  const root = fileURLToPath(new URL('..', import.meta.url))
  const env = loadEnv(mode, root, 'PERFAGENT_API_URL')
  const target = backendTarget({ ...env, ...process.env })
  return {
  plugins: [react()],
  server: {
    strictPort: true,
    proxy: {
      '/api': { target, changeOrigin: false },
      '/legacy': { target, changeOrigin: false },
    },
  },
  build: {
    outDir: '../src/perfagent/web/spa',
    emptyOutDir: true,
    sourcemap: false,
  },
  }
})
