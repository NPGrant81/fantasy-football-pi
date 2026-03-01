import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

// react-force-graph-2d is mocked globally in setupTests.jsx

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}));

import RivalryGraph from '../src/components/charts/RivalryGraph';
import apiClient from '../src/api/client';

describe('RivalryGraph', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('shows loading state initially', () => {
    apiClient.get.mockResolvedValue({ data: {} });
    render(<RivalryGraph />);
    expect(screen.getByText(/Loading rivalry graph/i)).toBeInTheDocument();
  });

  test('shows error when league_id is missing', async () => {
    apiClient.get.mockResolvedValueOnce({ data: {} }); // /auth/me returns no league_id

    render(<RivalryGraph />);

    await waitFor(() => {
      expect(screen.getByText(/League not found/i)).toBeInTheDocument();
    });
  });

  test('shows "no data" message when nodes array is empty', async () => {
    apiClient.get
      .mockResolvedValueOnce({ data: { league_id: 1 } }) // /auth/me
      .mockResolvedValueOnce({ data: { nodes: [], edges: [] } }); // /rivalry

    render(<RivalryGraph />);

    await waitFor(() => {
      expect(
        screen.getByText(/No rivalry data available/i)
      ).toBeInTheDocument();
    });
  });

  test('renders force graph with nodes when data is returned', async () => {
    apiClient.get
      .mockResolvedValueOnce({ data: { league_id: 5 } }) // /auth/me
      .mockResolvedValueOnce({
        data: {
          nodes: [
            { id: 1, label: 'Alice' },
            { id: 2, label: 'Bob' },
          ],
          edges: [
            {
              source: 1,
              target: 2,
              games: 10,
              trades: 2,
              wins: { '1': 6, '2': 4 },
            },
          ],
        },
      });

    render(<RivalryGraph />);

    await waitFor(() => {
      expect(screen.getByTestId('force-graph')).toBeInTheDocument();
    });

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  test('shows error message when API call fails', async () => {
    apiClient.get
      .mockResolvedValueOnce({ data: { league_id: 3 } }) // /auth/me
      .mockRejectedValueOnce(new Error('Network error')); // /rivalry

    render(<RivalryGraph />);

    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });
  });

  test('calls rivalry API with the league id from /auth/me', async () => {
    apiClient.get
      .mockResolvedValueOnce({ data: { league_id: 42 } })
      .mockResolvedValueOnce({ data: { nodes: [], edges: [] } });

    render(<RivalryGraph />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/analytics/league/42/rivalry');
    });
  });
});
