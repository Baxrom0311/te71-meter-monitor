import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg', 'apple-icon.png', 'icon-dark-32x32.png', 'icon-light-32x32.png'],
      manifest: {
        name: 'TE71 Meter Monitor',
        short_name: 'TE71 Meter',
        description: 'Elektr, suv va gaz monitoring platformasi',
        theme_color: '#030712',
        background_color: '#030712',
        display: 'standalone',
        orientation: 'portrait-primary',
        scope: '/',
        start_url: '/dashboard',
        lang: 'uz',
        categories: ['utilities', 'productivity', 'business'],
        icons: [
          {
            src: '/icon.svg',
            sizes: '180x180',
            type: 'image/svg+xml',
            purpose: 'any maskable',
          },
          {
            src: '/apple-icon.png',
            sizes: '180x180',
            type: 'image/png',
          },
        ],
      },
      workbox: {
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
        navigateFallback: '/index.html',
        globPatterns: ['**/*.{js,css,html,svg,png,ico,webp,woff2}'],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              networkTimeoutSeconds: 5,
              expiration: {
                maxEntries: 80,
                maxAgeSeconds: 60 * 10,
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/react-router-dom/')) {
            return 'vendor-react'
          }
          if (id.includes('@tanstack/react-query') || id.includes('axios')) {
            return 'vendor-data'
          }
          if (id.includes('recharts') || id.includes('d3-') || id.includes('victory-vendor')) {
            return 'vendor-charts'
          }
          if (id.includes('lucide-react')) {
            return 'vendor-icons'
          }
          if (id.includes('date-fns')) {
            return 'vendor-date'
          }
          return 'vendor'
        },
      },
    },
  },
})
