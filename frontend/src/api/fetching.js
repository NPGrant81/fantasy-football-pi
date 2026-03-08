import apiClient from '@api/client';

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function normalizeApiError(error, fallbackMessage = 'Request failed.') {
  const payload = error?.response?.data;
  if (typeof payload === 'string' && payload.trim()) {
    return payload;
  }
  if (payload?.detail) {
    return String(payload.detail);
  }
  if (payload?.message) {
    return String(payload.message);
  }
  if (error?.message) {
    return String(error.message);
  }
  return fallbackMessage;
}

function shouldRetry(error) {
  const status = Number(error?.response?.status || 0);
  if (!status) return true;
  return status === 408 || status === 425 || status === 429 || status >= 500;
}

export async function requestWithRetry({
  method = 'get',
  url,
  params,
  data,
  retries = 1,
  retryDelayMs = 300,
}) {
  let attempt = 0;
  let lastError;

  while (attempt <= retries) {
    try {
      const response = await apiClient.request({ method, url, params, data });
      return response?.data;
    } catch (error) {
      lastError = error;
      if (attempt >= retries || !shouldRetry(error)) {
        throw error;
      }
      await delay(retryDelayMs * (attempt + 1));
      attempt += 1;
    }
  }

  throw lastError;
}

export function getJson(url, options = {}) {
  return requestWithRetry({ method: 'get', url, ...options });
}

export function postJson(url, data, options = {}) {
  return requestWithRetry({ method: 'post', url, data, ...options });
}
