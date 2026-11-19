import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

const apiProxy = {
  '/api': {
    target: process.env.VITE_DEV_API_PROXY ?? 'http://localhost:5001',
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/favicon.svg', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'Potentiel',
        short_name: 'Potentiel',
        description: 'Raconte ta vie et repère les talents que tu as déjà.',
        lang: 'fr',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        background_color: '#fff8ec',
        theme_color: '#fff8ec',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: '/icons/maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // Seule l'interface est mise en cache : jamais les conversations ni les réponses de l'API.
        globPatterns: ['**/*.{js,css,html,svg,png,webp,woff2}'],
        // Néo et three.js ne sont téléchargés que par ceux qui l'affichent, puis gardés en cache.
        globIgnores: ['**/stage-*.js'],
        runtimeCaching: [
          {
            urlPattern: /\/assets\/(?:[^/]+\.glb|stage-[^/]+\.js)$/,
            handler: 'CacheFirst',
            options: { cacheName: 'neo', expiration: { maxEntries: 6 } },
          },
        ],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  server: { port: 5173, proxy: apiProxy },
  preview: { port: 4173, proxy: apiProxy },
});
