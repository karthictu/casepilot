/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import type { ProxyOptions } from 'vite'
import { defineConfig, loadEnv } from 'vite'

// Paths the dev server forwards to the casepilot API (see docs/api-reference.md).
const PROXIED_PATHS = ['/api', '/a2a', '/mcp', '/.well-known', '/health'] as const

function buildProxy(target: string): Record<string, ProxyOptions> {
  const proxy: Record<string, ProxyOptions> = {
    // The chat endpoint streams Server-Sent Events. Ask the upstream for an
    // uncompressed body and tell any intermediary not to buffer, so each
    // `data:` frame reaches the browser as soon as it is written.
    '/api/agui': {
      target,
      changeOrigin: true,
      configure(proxyServer) {
        proxyServer.on('proxyReq', (proxyReq) => {
          proxyReq.setHeader('accept-encoding', 'identity')
        })
        proxyServer.on('proxyRes', (proxyRes) => {
          proxyRes.headers['cache-control'] = 'no-cache, no-transform'
          proxyRes.headers['x-accel-buffering'] = 'no'
        })
      },
    },
  }
  for (const path of PROXIED_PATHS) {
    proxy[path] = { target, changeOrigin: true }
  }
  return proxy
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [react(), tailwindcss()],
    build: {
      // The chat route (assistant-ui + the AG-UI client) is a lazily loaded
      // ~650 kB chunk; everything else stays well under the default 500 kB.
      chunkSizeWarningLimit: 800,
    },
    server: {
      port: 5173,
      proxy: buildProxy(target),
    },
    preview: {
      port: 4173,
      proxy: buildProxy(target),
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      restoreMocks: true,
    },
  }
})
