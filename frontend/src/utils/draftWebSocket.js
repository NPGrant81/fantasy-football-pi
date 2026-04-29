export function buildDraftWebSocketUrl(sessionId) {
  const fromEnv =
    import.meta?.env?.VITE_API_BASE_URL ||
    import.meta?.env?.VITE_API_PROXY_TARGET ||
    window.location.origin;

  const base = new URL(fromEnv, window.location.origin);
  base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
  base.pathname = `/draft/ws/${encodeURIComponent(sessionId)}`;
  base.search = '';
  base.hash = '';
  return base.toString();
}
