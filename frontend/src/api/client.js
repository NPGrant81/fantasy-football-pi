// frontend/src/api/client.js
import axios from 'axios';

const CSRF_COOKIE_NAME = 'ffpi_csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';

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

// --- 2.1 REQUEST INTERCEPTOR (The Key Holder) ---
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('fantasyToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

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

// --- 2.2 RESPONSE INTERCEPTOR (The Auto-Logout) ---
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 2.2.1 If the server says "Unauthorized" (401), wipe the session
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('fantasyToken');
      localStorage.removeItem('authMode');
      // 2.2.2 Force a refresh to trigger the Path A (Login) in App.jsx
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
