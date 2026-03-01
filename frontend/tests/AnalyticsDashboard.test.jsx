import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}));

vi.mock('react-router-dom', () => ({
  Link: ({ to, children, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

import AnalyticsDashboard from '../src/pages/Analytics/AnalyticsDashboard';
import apiClient from '../src/api/client';

describe('AnalyticsDashboard', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
  });

  test('renders header and buttons', () => {
    render(<AnalyticsDashboard />);
    expect(screen.getByText(/League Analytics/i)).toBeInTheDocument();
    expect(screen.getByText(/Draft Value Analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/Efficiency Leaderboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Manager Performance Trends/i)).toBeInTheDocument();
    expect(screen.getByText(/Trade Analyzer/i)).toBeInTheDocument();
    expect(screen.getByText(/League Rivalry Graph/i)).toBeInTheDocument();
  });

  test('shows efficiency leaderboard after clicking and fetches data', async () => {
    // first call returns user info
    apiClient.get
      .mockResolvedValueOnce({ data: { user_id: 5, league_id: 10 } })
      // second call returns leaderboard rows
      .mockResolvedValueOnce({
        data: [
          {
            manager_id: 5,
            efficiency_display: '94.2%',
            personality: 'Tactician',
          },
        ],
      });

    render(<AnalyticsDashboard />);

    fireEvent.click(screen.getByText(/Efficiency Leaderboard/i));

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    });
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        '/analytics/league/10/leaderboard'
      );
    });

    expect(await screen.findByText('94.2%')).toBeInTheDocument();
    expect(screen.getByText(/Tactician/i)).toBeInTheDocument();
  });

  test('loads manager trend chart data on click', async () => {
    apiClient.get
      .mockResolvedValueOnce({ data: { user_id: 7, league_id: 12 } })
      .mockResolvedValueOnce({
        data: [
          { week: 1, actual: 100, max: 110, efficiency: 0.91 },
          { week: 2, actual: 105, max: 120, efficiency: 0.875 },
        ],
      });

    render(<AnalyticsDashboard />);
    fireEvent.click(screen.getByText(/Manager Performance Trends/i));

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    });
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        '/analytics/league/12/weekly-stats',
        { params: { manager_id: 7 } }
      );
    });

    // loading message should disappear
    await waitFor(() =>
      expect(screen.queryByText(/Loading trend chart/i)).not.toBeInTheDocument()
    );
  });

  test('trade analyzer button updates selection', async () => {
    render(<AnalyticsDashboard />);
    fireEvent.click(screen.getByText(/Trade Analyzer/i));
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  test('league rivalry graph button shows rivalry graph', async () => {
    apiClient.get
      .mockResolvedValueOnce({ data: { league_id: 7 } })
      .mockResolvedValueOnce({
        data: {
          nodes: [
            { id: 1, label: 'Alice' },
            { id: 2, label: 'Bob' },
          ],
          edges: [{ source: 1, target: 2, games: 5, trades: 1, wins: {} }],
        },
      });

    render(<AnalyticsDashboard />);
    fireEvent.click(screen.getByText(/League Rivalry Graph/i));

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/analytics/league/7/rivalry');
    });

    await waitFor(() => {
      expect(screen.getByTestId('force-graph')).toBeInTheDocument();
    });
  });
});
