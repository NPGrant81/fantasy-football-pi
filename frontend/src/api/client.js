// frontend/src/api/client.js
import axios from 'axios';

// --- 1.1 CONFIGURATION ---
const apiClient = axios.create({
  // 1.1.1 Use environment variables if available, fallback to localhost for Pi dev
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000', 
  timeout: 8000, // Increased to 8s for slower Raspberry Pi responses
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