import { render, screen, waitFor } from '@testing-library/react';
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

import ManagerTrendChart from '../src/components/charts/ManagerTrendChart';
import apiClient from '../src/api/client';

describe('ManagerTrendChart', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('renders without crashing when API returns non-array stats', async () => {
    apiClient.get.mockResolvedValue({ data: { league_id: 1, user_id: 1 } });
    // first call is /auth/me, second is the analytics endpoint
    apiClient.get.mockImplementationOnce(() =>
      Promise.resolve({ data: { league_id: 1, user_id: 1 } })
    );
    apiClient.get.mockImplementationOnce(() =>
      Promise.resolve({ data: { error: 'no data' } })
    );

    render(<ManagerTrendChart />);

    // component should render the chart container (heading) without crashing
    await waitFor(() => {
      expect(
        screen.getByText(/Manager Performance Trends/i)
      ).toBeInTheDocument();
    });
  });
});
