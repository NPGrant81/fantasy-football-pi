// @vitest-environment node
import { readFileSync } from 'node:fs';
import { createServer as createHttpServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { createServer as createViteServer } from 'vite';
import { describe, expect, it } from 'vitest';
import { bypassDocumentRequest, createApiProxy } from '../config/apiProxy';

const nginx = readFileSync(new URL('../../deploy/nginx/fantasy-football-pi.conf.example', import.meta.url), 'utf8');
const nginxPattern = new RegExp(nginx.match(/location ~ (\S+) \{/)[1]);
const proxy = createApiProxy('http://127.0.0.1:8010');
const matchesVite = (path) => Object.keys(proxy).some((pattern) => new RegExp(pattern.slice(1)).test(path));

describe('API and SPA ingress ownership', () => {
  it.each([
    '/news/global', '/live-scoring/stream', '/admin/nfl/sync',
    '/admin/live-scoring/status', '/admin/drafts/refresh-values',
    '/admin/config/reload', '/waivers/claims', '/draft/pick',
    '/team/1', '/analytics/league/1/luck-index', '/api/etl/run',
    '/players?limit=10', '/leagues?season=2026', '/news?limit=5',
  ])('proxies API path %s in both environments', (path) => {
    expect(matchesVite(path)).toBe(true);
    expect(nginxPattern.test(path.split('?')[0])).toBe(true);
    expect(bypassDocumentRequest({ method: 'GET', headers: { accept: 'application/json' } })).toBeUndefined();
  });

  it.each(['/draft', '/team/1', '/trades/submit', '/analytics', '/waivers', '/keepers'])(
    'serves the SPA for document navigation to %s',
    () => {
      expect(bypassDocumentRequest({ method: 'GET', headers: { accept: 'text/html,application/xhtml+xml' } })).toBe('/index.html');
      expect(bypassDocumentRequest({ method: 'HEAD', headers: { accept: 'text/html' } })).toBe('/index.html');
      expect(nginx).toContain('if ($spa_document_request)');
      expect(nginx).toContain('rewrite ^ /index.html last;');
      expect(nginx).toContain('~^(GET|HEAD):.*text/html 1;');
    }
  );

  it('does not hijack API writes or unrelated page prefixes', () => {
    expect(bypassDocumentRequest({ method: 'POST', headers: { accept: 'text/html' } })).toBeUndefined();
    expect(matchesVite('/league-history')).toBe(false);
    expect(matchesVite('/draft-day-analyzer')).toBe(false);
    expect(nginxPattern.test('/draft-day-analyzer')).toBe(false);
  });

  it('serves actual JSON, SSE and SPA documents through Vite', async () => {
    const backend = createHttpServer((request, response) => {
      if (request.url.startsWith('/live-scoring/')) {
        response.writeHead(200, { 'Content-Type': 'text/event-stream' });
        response.end('event: connected\ndata: {}\n\n');
      } else {
        response.writeHead(200, { 'Content-Type': 'application/json' });
        response.end(JSON.stringify([{ title: 'News reached backend' }]));
      }
    });
    await new Promise((resolve) => backend.listen(0, '127.0.0.1', resolve));
    let vite;
    try {
      vite = await createViteServer({
        configFile: false,
        root: fileURLToPath(new URL('..', import.meta.url)),
        optimizeDeps: { noDiscovery: true, include: [] },
        server: {
          host: '127.0.0.1',
          port: 0,
          proxy: createApiProxy(`http://127.0.0.1:${backend.address().port}`),
          watch: null,
        },
      });
      await vite.listen();
      const base = `http://127.0.0.1:${vite.httpServer.address().port}`;
      for (const path of ['/news/global', '/players?limit=10', '/leagues?season=2026']) {
        const news = await fetch(`${base}${path}`, { headers: { Accept: 'application/json' } });
        expect(news.headers.get('content-type')).toContain('application/json');
        expect(await news.json()).toEqual([{ title: 'News reached backend' }]);
      }
      const stream = await fetch(`${base}/live-scoring/stream`);
      expect(stream.headers.get('content-type')).toContain('text/event-stream');
      expect(await stream.text()).toContain('event: connected');
      for (const path of ['/team/1', '/trades/submit', '/analytics']) {
        const document = await fetch(`${base}${path}`, { headers: { Accept: 'text/html' } });
        expect(document.status).toBe(200);
        expect(document.headers.get('content-type')).toContain('text/html');
        expect(await document.text()).toContain('<!doctype html>');
      }
    } finally {
      await vite?.close();
      backend.closeAllConnections();
      await new Promise((resolve) => backend.close(resolve));
    }
  });
});
