import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => {
  const client = {
    get: vi.fn(),
  };
  client.request = vi.fn((config = {}) => {
    const method = String(config.method || 'get').toLowerCase();
    const handler = client[method];
    if (typeof handler !== 'function') {
      return Promise.reject(new Error(`Unsupported method: ${method}`));
    }
    if (config.params !== undefined || config.data !== undefined) {
      return handler(config.url, { params: config.params, data: config.data });
    }
    return handler(config.url);
  });
  return { default: client };
});

import TradeAnalyzer from '../src/components/charts/TradeAnalyzer';
import apiClient from '../src/api/client';

describe('TradeAnalyzer component', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
  });

  test('loads owners and displays selects', async () => {
    const user = userEvent.setup();
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me')
        return Promise.resolve({ data: { league_id: 1 } });
      if (url.startsWith('/leagues/owners'))
        return Promise.resolve({ data: [{ id: 1, username: 'A' }, { id: 2, username: 'B' }] });
      if (url.startsWith('/team/'))
        return Promise.resolve({
          data: {
            players: [
              { player_id: 101, name: 'Test QB', position: 'QB', projected_points: 18.5 },
            ],
          },
        });
      return Promise.reject(new Error('unknown'));
    });

    render(<TradeAnalyzer />);

    await waitFor(() =>
      expect(screen.getByLabelText(/Team A selector/i)).toBeInTheDocument()
    );
    // simulate choosing owner
    await user.selectOptions(screen.getByLabelText(/Team A selector/i), '1');
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/team/1', expect.any(Object)));
  });

  test('shows conflict error when Team A and Team B match', async () => {
    const user = userEvent.setup();
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') return Promise.resolve({ data: { league_id: 1 } });
      if (url.startsWith('/leagues/owners')) {
        return Promise.resolve({ data: [{ id: 1, username: 'A' }, { id: 2, username: 'B' }] });
      }
      if (url.startsWith('/team/')) return Promise.resolve({ data: { players: [] } });
      return Promise.reject(new Error('unknown'));
    });

    render(<TradeAnalyzer />);

    await waitFor(() => expect(screen.getByLabelText(/Team A selector/i)).toBeInTheDocument());
    await user.selectOptions(screen.getByLabelText(/Team B selector/i), '1');

    await waitFor(() => {
      expect(screen.getByText(/Team A and Team B must be different teams/i)).toBeInTheDocument();
    });
  });

  test('handles malformed roster payloads without crashing', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') return Promise.resolve({ data: { league_id: 1 } });
      if (url.startsWith('/leagues/owners')) {
        return Promise.resolve({ data: [{ id: 1, username: 'A' }, { id: 2, username: 'B' }] });
      }
      if (url === '/team/1') return Promise.resolve({ data: { players: null } });
      if (url === '/team/2') return Promise.resolve({ data: {} });
      return Promise.reject(new Error('unknown'));
    });

    render(<TradeAnalyzer />);

    await waitFor(() => expect(screen.getByLabelText(/Team A selector/i)).toBeInTheDocument());
    await waitFor(() => {
      const emptyMessages = screen.getAllByText(/No players match current filter/i);
      expect(emptyMessages.length).toBeGreaterThan(0);
    });
  });
});
