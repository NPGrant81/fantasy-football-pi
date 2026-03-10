import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

// --- 1.1 ENVIRONMENT SETUP ---
// 1.1.1 ESM Polyfill: Defining __dirname for Vite/ESM compatibility
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '');
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8010';

  return {
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
      '/auth': apiTarget,
      '/draft/': apiTarget,
      '/draft/pick': apiTarget,
      '/draft/history': apiTarget,
      // only proxy the actual admin API endpoints; the client-side UI also uses
      // /admin paths, so forwarding everything breaks SPA routing (see
      // Manage Commissioners page). narrowing prevents 404s on reload.
      '/admin/tools': apiTarget,
      '/admin/create-test-league': apiTarget,
      '/admin/reset-draft': apiTarget,
      '/team/': apiTarget,
      '/league': apiTarget,
      '/leagues': apiTarget,
      '/players': apiTarget,
      '/advisor': apiTarget,
      '/dashboard': apiTarget,
      '/waivers/': apiTarget,
      '/trades': apiTarget,
      '/scoring': apiTarget,
      '/keepers/': apiTarget,
      '/playoffs/': apiTarget,
      '/analytics/': apiTarget,
      '/nfl': apiTarget,
      '/feedback': apiTarget,
      '/bug-reports': apiTarget,
      '/etl': apiTarget,
      '/matchups/': apiTarget,
      },
    },
  };
});
