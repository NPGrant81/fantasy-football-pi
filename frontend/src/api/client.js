// frontend/src/api/client.js
import axios from 'axios';

const CSRF_COOKIE_NAME = 'ffpi_csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const REFRESH_ENDPOINT = '/auth/refresh';

let refreshPromise = null;

function getCookieValue(name) {
  if (typeof document === 'undefined') return null;
  const encodedName = `${encodeURIComponent(name)}=`;
  const parts = document.cookie ? document.cookie.split('; ') : [];
  for (const part of parts) {
    if (part.startsWith(encodedName)) {
      return decodeURIComponent(part.slice(encodedName.length));
    }
  }
  return null;
}

// --- 1.1 CONFIGURATION ---
const apiClient = axios.create({
  // 1.1.1 Use env var when explicitly provided (production builds) otherwise
  // default to a relative base so Vite's dev proxy can handle the request.
  // Setting the var to an empty string is also acceptable.
  // guard against import.meta.env being undefined in test environments
  baseURL: import.meta?.env?.VITE_API_BASE_URL || '',
  timeout: 30000, // 30s default to tolerate slower local/AI-backed responses
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

function normalizePath(url) {
  if (!url) return '';
  if (typeof url !== 'string') return '';
  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      return new URL(url).pathname;
    } catch {
      return url;
    }
  }
  return url;
}

function shouldAttemptRefresh(error) {
  const status = Number(error?.response?.status || 0);
  if (status !== 401) return false;

  const config = error?.config || {};
  if (config._skipAuthRefresh || config._authRetryAttempted) return false;

  const requestPath = normalizePath(config.url);
  if (requestPath === REFRESH_ENDPOINT || requestPath === '/auth/token' || requestPath === '/auth/logout') {
    return false;
  }

  return true;
}

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = apiClient.post(
      REFRESH_ENDPOINT,
      {},
      { _skipAuthRefresh: true }
    ).finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

// --- 2.1 REQUEST INTERCEPTOR (Cookie + CSRF) ---
apiClient.interceptors.request.use(
  (config) => {
    const method = (config.method || 'get').toUpperCase();
    const isStateChanging = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method);
    if (isStateChanging) {
      const csrfToken = getCookieValue(CSRF_COOKIE_NAME);
      if (csrfToken) {
        config.headers[CSRF_HEADER_NAME] = csrfToken;
      }
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// --- 2.2 RESPONSE INTERCEPTOR ---
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (shouldAttemptRefresh(error)) {
      const originalConfig = error.config;
      originalConfig._authRetryAttempted = true;

      try {
        await refreshAccessToken();
        return apiClient.request(originalConfig);
      } catch (_refreshError) {
        // Fall through to component/App-level auth handling if refresh fails.
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
