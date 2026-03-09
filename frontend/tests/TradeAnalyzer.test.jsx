import { render, screen, waitFor, fireEvent } from '@testing-library/react';
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
    fireEvent.change(screen.getByLabelText(/Team A selector/i), { target: { value: '1' } });
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/team/1', expect.any(Object)));
  });
});
