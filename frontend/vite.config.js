import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path' // Required for aliasing

export default defineConfig({
  plugins: [react()],
  resolve: {
    // MERGED: Adding your professional path aliases
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@api': path.resolve(__dirname, './src/api'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@utils': path.resolve(__dirname, './src/utils'),
    },
  },
  server: {
    proxy: {
      // PRO MOVE: Instead of listing every route, proxy everything starting with /api
      // Or, if you prefer individual routes to match your current setup:
      '/auth': 'http://127.0.0.1:8000',
      '/draft': 'http://127.0.0.1:8000',
      '/admin': 'http://127.0.0.1:8000',
      '/league': 'http://127.0.0.1:8000',
      '/players': 'http://127.0.0.1:8000',
      '/advisor': 'http://127.0.0.1:8000',
    }
  }
})