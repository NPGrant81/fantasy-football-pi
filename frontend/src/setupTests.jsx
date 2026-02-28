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

// jsdom doesn't implement matchMedia; provide a minimal polyfill
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  });
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

// Stub out chart libraries to prevent jsdom canvas errors during tests
vi.mock('chart.js', () => {
  // minimal dummy Chart class
  return {
    Chart: class {
      constructor(_ctx, _config) {
        // nothing
      }
      static register() {}
      update() {}
      destroy() {}
    },
    // provide any functions that might be called
    defaults: { global: {} },
  };
});

vi.mock('react-chartjs-2', () => {
  const React = vi.importActual('react');
  // provide basic components that render placeholders
  return {
    Scatter: (props) => React.default.createElement('div', { 'data-testid': 'scatter-chart' }),
    Bar: (props) => React.default.createElement('div', { 'data-testid': 'bar-chart' }),
    Line: (props) => React.default.createElement('div', { 'data-testid': 'line-chart' }),
    Doughnut: (props) => React.default.createElement('div', { 'data-testid': 'doughnut-chart' }),
    Pie: (props) => React.default.createElement('div', { 'data-testid': 'pie-chart' }),
    // forward others if necessary
  };
});

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
export * from '@testing-library/react';
export { render, mockNavigate };
