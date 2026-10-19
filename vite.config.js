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
      // Paridad con nginx de prod (nginx.conf): admin de Django y sus estáticos.
      // changeOrigin: false conserva el Host "localhost" — con true Django ve
      // "api:8000" y el login admin muere en verificación CSRF (403).
      '/admin': {
        target: 'http://api:8000',
        changeOrigin: false,
      },
      '/static': {
        target: 'http://api:8000',
        changeOrigin: false,
      },
    },
  },
});
