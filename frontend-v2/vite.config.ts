import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite config for UI Modernization V2 (batch 1).
// - Hash routing is used in the app, so `base` only affects asset URLs.
// - Dev server proxies /api to the local backend (http://localhost:8000) to avoid CORS
//   and keeps the backend untouched.
// - base defaults to '/'. `npm run dev` and `npm run build` serve at '/';
//   `npm run build:preview` overrides VITE_BASE to '/preview/' for the /preview mount.
export default defineConfig({
  base: process.env.VITE_BASE ?? '/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    // vendor chunk splitting (batch 3): pull the heavy/3rd-party libs out of the
    // main entry so the main chunk stays well under 500KB. happy-dom is a
    // dev/test-only dependency and is never part of the production bundle, so it
    // is intentionally ignored here.
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) return 'echarts'
          if (
            id.includes('node_modules/vue') ||
            id.includes('node_modules/@vue') ||
            id.includes('node_modules/pinia') ||
            id.includes('node_modules/vue-router')
          ) {
            return 'vue-vendor'
          }
          if (id.includes('node_modules/lucide-vue-next')) return 'icons'
          return undefined
        },
      },
    },
  },
})
