import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

// --- 1.1 ENVIRONMENT SETUP ---
// 1.1.1 ESM Polyfill: Defining __dirname for Vite/ESM compatibility
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export default defineConfig({
  plugins: [react()],
  
  // --- 2.1 PATH RESOLUTION ---
  resolve: {
    // 2.1.1 Aliasing: Simplifies imports (e.g., import X from '@/components/X')
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@api': path.resolve(__dirname, './src/api'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@utils': path.resolve(__dirname, './src/utils'),
    },
  },

  // --- 3.1 DEVELOPMENT SERVER ---
  server: {
    proxy: {
      // 3.1.1 Proxy Rules: Routes API calls to your Raspberry Pi / Local Python Backend
      '/auth': 'http://127.0.0.1:8000',
      '/draft': 'http://127.0.0.1:8000',
      '/admin': 'http://127.0.0.1:8000',
      '/league': 'http://127.0.0.1:8000',
      '/players': 'http://127.0.0.1:8000',
      '/advisor': 'http://127.0.0.1:8000',
    }
  }
})