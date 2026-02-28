import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}));

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
      if (url.startsWith('/analytics/roster-strength'))
        return Promise.resolve({ data: { 1: { QB: 1, RB: 2, WR: 0, TE: 0 } } });
      return Promise.reject(new Error('unknown'));
    });

    render(<TradeAnalyzer />);

    await waitFor(() =>
      expect(screen.getByLabelText(/Owner A/i)).toBeInTheDocument()
    );
    // simulate choosing owner
    fireEvent.change(screen.getByLabelText(/Owner A/i), { target: { value: '1' } });
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/analytics/roster-strength', expect.any(Object)));
  });
});
