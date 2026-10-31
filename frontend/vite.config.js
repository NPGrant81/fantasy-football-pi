import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import { createApiProxy } from './config/apiProxy.js';

// --- 1.1 ENVIRONMENT SETUP ---
// 1.1.1 ESM Polyfill: Defining __dirname for Vite/ESM compatibility
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8010';
  return {
    plugins: [react()],

  // --- 2.1 PATH RESOLUTION ---
    resolve: {
    // 2.1.1 Aliasing: Simplifies imports (e.g., import X from '@/components/X')
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@api': path.resolve(__dirname, './src/api'),
      '@context': path.resolve(__dirname, './src/context'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@utils': path.resolve(__dirname, './src/utils'),
    },
  },

  // --- 3.1 DEVELOPMENT SERVER ---
    server: {
      proxy: createApiProxy(apiProxyTarget),
    },
  };
});
