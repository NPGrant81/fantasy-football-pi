import '@testing-library/jest-dom';
import { vi } from 'vitest';

// bring in testing-library and router helpers before any code runs
import * as rtl from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

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

// override the default render helper to always mount components inside a
// router; this spares every individual test from having to wrap with a
// MemoryRouter and resolves the "basename" destructuring error mentioned by
// CI logs.

const originalRender = rtl.render;
function render(ui, options) {
  return originalRender(<MemoryRouter>{ui}</MemoryRouter>, options);
}

// re-export everything from testing-library and override render
export * from rtl;
export { render, mockNavigate };