import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // This tells the frontend: "If you see a request for /leagues, send it to Python port 8000"
      '/leagues': 'http://127.0.0.1:8000',
      '/owners': 'http://127.0.0.1:8000',
      '/draft-pick': 'http://127.0.0.1:8000',
      '/advisor': 'http://127.0.0.1:8000',
    }
  }
})