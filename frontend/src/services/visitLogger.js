import apiClient from '@api/client';

const SESSION_KEY = 'ffpi_visit_session_id';
let cachedSessionId = null;

function generateSessionId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export function getVisitSessionId() {
  if (cachedSessionId) return cachedSessionId;

  if (typeof window === 'undefined') {
    cachedSessionId = generateSessionId();
    return cachedSessionId;
  }

  const existing = window.sessionStorage.getItem(SESSION_KEY);
  if (existing) {
    cachedSessionId = existing;
    return existing;
  }

  const sessionId = generateSessionId();
  window.sessionStorage.setItem(SESSION_KEY, sessionId);
  cachedSessionId = sessionId;
  return sessionId;
}

export function emitVisitEvent(path, userId = null) {
  if (!path) return;

  const payload = {
    timestamp: new Date().toISOString(),
    path,
    userId,
    sessionId: getVisitSessionId(),
    userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : null,
    referrer: typeof document !== 'undefined' ? document.referrer || null : null,
  };

  if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      const base = apiClient.defaults?.baseURL || '';
      const url = `${base}/analytics/visit`;
      const body = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      const sent = navigator.sendBeacon(url, body);
      if (sent) return;
    } catch {
      // fall through to axios fire-and-forget path
    }
  }

  try {
    const request = apiClient.post('/analytics/visit', payload);
    if (request && typeof request.catch === 'function') {
      request.catch(() => {});
    }
  } catch {
    // swallow sync errors to keep logging non-blocking
  }
}
