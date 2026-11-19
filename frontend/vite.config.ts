import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: process.env.PERFAGENT_API_URL || 'http://127.0.0.1:8000', changeOrigin: true },
      '/legacy': { target: process.env.PERFAGENT_API_URL || 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: '../src/perfagent/web/spa',
    emptyOutDir: true,
    sourcemap: false,
  },
})
