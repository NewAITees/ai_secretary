import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Read backend port from environment variable, default to 8001
const backendPort = process.env.VITE_BACKEND_PORT || '8001';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
});
