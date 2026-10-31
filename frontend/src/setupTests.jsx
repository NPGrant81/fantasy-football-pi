import '@testing-library/jest-dom';
import { afterEach, vi } from 'vitest';
import React from 'react';

const { queryClients } = vi.hoisted(() => ({ queryClients: new Set() }));

vi.mock('@testing-library/react', async () => {
  const actual = await vi.importActual('@testing-library/react');
  const { QueryClient, QueryClientProvider } = await vi.importActual('@tanstack/react-query');
  const { createElement } = await vi.importActual('react');
  function withQueryProvider(options = {}) {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: Infinity },
        mutations: { retry: false },
      },
    });
    queryClients.add(client);
    const CustomWrapper = options.wrapper;
    const wrapper = ({ children }) => createElement(
      QueryClientProvider,
      { client },
      CustomWrapper ? createElement(CustomWrapper, null, children) : children
    );
    return { ...options, wrapper };
  }
  return {
    ...actual,
    render: (ui, options) => actual.render(ui, withQueryProvider(options)),
    renderHook: (hook, options) => actual.renderHook(hook, withQueryProvider(options)),
  };
});

afterEach(() => {
  rtl.cleanup();
  queryClients.forEach((client) => client.clear());
  queryClients.clear();
});

// bring in testing-library and router helpers before any code runs
import * as rtl from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock react-force-graph-2d globally since it uses canvas (not available in jsdom)
vi.mock('react-force-graph-2d', () => ({
  default: ({ graphData, nodeLabel }) => (
    <div data-testid="force-graph">
      {(graphData?.nodes || []).map((n) => (
        <span key={n.id}>{(nodeLabel && n[nodeLabel]) || n.id}</span>
      ))}
    </div>
  ),
}));


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
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

// Stub out chart libraries to prevent jsdom canvas errors during tests
vi.mock('chart.js', async () => {
  // import the actual module so we preserve all exports, then override Chart
  const actual = await vi.importActual('chart.js');
  class DummyChart {
    constructor(_ctx, _config) {
      // no-op
    }
    static register() {}
    update() {}
    destroy() {}
  }
  return {
    ...actual,
    Chart: DummyChart,
  };
});

vi.mock('react-chartjs-2', () => {
  // provide basic components that render placeholders
  return {
    Scatter: (_props) =>
      React.createElement('div', { 'data-testid': 'scatter-chart' }),
    Bar: (_props) => React.createElement('div', { 'data-testid': 'bar-chart' }),
    Line: (_props) =>
      React.createElement('div', { 'data-testid': 'line-chart' }),
    Doughnut: (_props) =>
      React.createElement('div', { 'data-testid': 'doughnut-chart' }),
    Pie: (_props) => React.createElement('div', { 'data-testid': 'pie-chart' }),
    Radar: (_props) =>
      React.createElement('div', { 'data-testid': 'radar-chart' }),
    // forward others if necessary
  };
});

// Mock force-graph libraries to avoid canvas usage in tests
vi.mock('react-force-graph', () => ({
  ForceGraph2D: ({ graphData, nodeLabel }) => (
    <div data-testid="force-graph">
      {(graphData?.nodes || []).map((n) => (
        <span key={n.id}>{(nodeLabel && n[nodeLabel]) || n.id}</span>
      ))}
    </div>
  ),
}));
vi.mock('react-force-graph-2d', () => ({
  __esModule: true,
  default: ({ graphData, nodeLabel }) => (
    <div data-testid="force-graph">
      {(graphData?.nodes || []).map((n) => (
        <span key={n.id}>{(nodeLabel && n[nodeLabel]) || n.id}</span>
      ))}
    </div>
  ),
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
// eslint-disable-next-line react-refresh/only-export-components
export * from '@testing-library/react';
export { render, mockNavigate };
