// frontend/src/api/client.js
import axios from 'axios';

// --- 1.1 CONFIGURATION ---
const apiClient = axios.create({
  // 1.1.1 Use env var when explicitly provided (production builds) otherwise
  // default to a relative base so Vite's dev proxy can handle the request.
  // Setting the var to an empty string is also acceptable.
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000, // 30s default to tolerate slower local/AI-backed responses
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- 2.1 REQUEST INTERCEPTOR (The Key Holder) ---
apiClient.interceptors.request.use(
  (config) => {
    // 2.1.1 Automatically grab the token from storage
    const token = localStorage.getItem('fantasyToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
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
      // 2.2.2 Force a refresh to trigger the Path A (Login) in App.jsx
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
