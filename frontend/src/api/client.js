// src/api/client.js
import axios from 'axios';

// Create a reusable Axios instance
const apiClient = axios.create({
  // Your backend's home address
  baseURL: 'http://127.0.0.1:8000', 
  timeout: 5000, // Wait 5 seconds before giving up
  headers: {
    'Content-Type': 'application/json',
  },
});

export default apiClient;