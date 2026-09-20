import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true, // dev: permite túneles (trycloudflare) y dominios
    watch: {
      usePolling: true,
      interval: 2000,
      ignored: ['**/node_modules/**', '**/.git/**', '**/.venv/**', '**/dist/**', '**/__pycache__/**'],
    },
    proxy: {
      '/api': {
        target: 'http://api:8000',
        changeOrigin: true,
        rewrite: (path) => path,
      },
      '/ws': {
        target: 'ws://api:8000',
        ws: true,
        changeOrigin: true,
      },
      '/media': {
        target: 'http://api:8000',
        changeOrigin: true,
      },
    },
  },
});
