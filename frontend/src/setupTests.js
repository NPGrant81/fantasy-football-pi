import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Provide a basic mock for localStorage in case the environment is missing it
if (!global.localStorage) {
  const storage = {};
  global.localStorage = {
    getItem: (key) => (key in storage ? storage[key] : null),
    setItem: (key, value) => (storage[key] = String(value)),
    removeItem: (key) => delete storage[key],
    clear: () => Object.keys(storage).forEach((k) => delete storage[k]),
  };
}

// === Global mocks for all tests ===
// Mock the API client so individual files don't need to repeat this.
vi.mock('./api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

// Keep a reusable navigate mock that tests can inspect if needed.
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

export { mockNavigate };
