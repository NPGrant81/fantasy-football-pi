import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

vi.mock('react-router-dom', () => ({
  useParams: () => ({ id: undefined }),
  Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
}));

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}));

import Matchups from '../src/pages/Matchups';
import apiClient from '../src/api/client';

describe('Matchups (Weekly Matchups)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders week selector header and current user/league info', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { username: 'alice', league_id: 1 },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/matchups/week/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Matchups />);

    await waitFor(() => {
      expect(screen.getByText(/alice/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/The Big Show/i)).toBeInTheDocument();
  });

  test('loads and displays week 1 matchups on mount', async () => {
    const mockGames = [
      {
        id: 1,
        week: 1,
        home_team: 'Team A',
        away_team: 'Team B',
        home_score: 110,
        away_score: 95,
        home_projected: 120,
        away_projected: 100,
      },
      {
        id: 2,
        week: 1,
        home_team: 'Team C',
        away_team: 'Team D',
        home_score: 105,
        away_score: 108,
        home_projected: 100,
        away_projected: 110,
      },
    ];

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { username: 'alice', league_id: 1 },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/matchups/week/1') {
        return Promise.resolve({ data: mockGames });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Matchups />);

    await waitFor(() => {
      expect(screen.getByText('Team A')).toBeInTheDocument();
    });
    expect(screen.getByText('Team B')).toBeInTheDocument();
    expect(screen.getByText('Team C')).toBeInTheDocument();
    expect(screen.getByText('Team D')).toBeInTheDocument();
  });

  test('displays projected scores by default', async () => {
    const mockGames = [
      {
        id: 1,
        week: 1,
        home_team: 'Team A',
        away_team: 'Team B',
        home_score: 110,
        away_score: 95,
        home_projected: 120,
        away_projected: 100,
      },
    ];

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { username: 'alice', league_id: 1 },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/matchups/week/1') {
        return Promise.resolve({ data: mockGames });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Matchups />);

    await waitFor(() => {
      expect(screen.getByText('120')).toBeInTheDocument(); // Projected home
    });
    expect(screen.getByText('100')).toBeInTheDocument(); // Projected away
  });

  test('toggles between projected and actual scores', async () => {
    const mockGames = [
      {
        id: 1,
        week: 1,
        home_team: 'Team A',
        away_team: 'Team B',
        home_score: 110,
        away_score: 95,
        home_projected: 120,
        away_projected: 100,
      },
    ];

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { username: 'alice', league_id: 1 },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/matchups/week/1') {
        return Promise.resolve({ data: mockGames });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Matchups />);

    await waitFor(() => {
      expect(screen.getByText('120')).toBeInTheDocument(); // Projected
    });

    const toggleButton = screen.getByLabelText(/Toggle projected scores/i);
    const user = userEvent.setup();
    await user.click(toggleButton);

    // Should now show actual scores
    await waitFor(() => {
      expect(screen.getByText('110')).toBeInTheDocument(); // Actual home
    });
  });

  test('navigates to next week when clicking next button', async () => {
    const mockGamesWeek1 = [
      {
        id: 1,
        week: 1,
        home_team: 'Team A',
        away_team: 'Team B',
        home_score: 100,
        away_score: 95,
        home_projected: 120,
        away_projected: 100,
      },
    ];

    const mockGamesWeek2 = [
      {
        id: 2,
        week: 2,
        home_team: 'Team C',
        away_team: 'Team D',
        home_score: 105,
        away_score: 108,
        home_projected: 100,
        away_projected: 110,
      },
    ];

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { username: 'alice', league_id: 1 },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/matchups/week/1') {
        return Promise.resolve({ data: mockGamesWeek1 });
      }
      if (url === '/matchups/week/2') {
        return Promise.resolve({ data: mockGamesWeek2 });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Matchups />);

    await waitFor(() => {
      expect(screen.getByText('Team A')).toBeInTheDocument();
    });

    const nextButton = screen.getByLabelText(/Next week/i);
    const user = userEvent.setup();
    await user.click(nextButton);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/matchups/week/2');
    });
  });

  test('disables previous button when on week 1', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { username: 'alice', league_id: 1 },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/matchups/week/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Matchups />);

    await waitFor(() => {
      const prevButton = screen.getByLabelText(/Previous week/i);
      expect(prevButton).toBeDisabled();
    });
  });

  test('next button is enabled on week 1', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { username: 'alice', league_id: 1 },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url.includes('/matchups/week/')) {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Matchups />);

    await waitFor(() => {
      const nextButton = screen.getByLabelText(/Next week/i);
      expect(nextButton).not.toBeDisabled();
    });
  });

  test('shows loading indicator while fetching matchups', async () => {
    let resolveMatchups;
    const matchupsPromise = new Promise((resolve) => {
      resolveMatchups = resolve;
    });

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { username: 'alice', league_id: 1 },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url.includes('/matchups/week/')) {
        return matchupsPromise;
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Matchups />);

    // At startup, should show loading (component initializes with loading: true)
    await waitFor(() => {
      expect(screen.getByText(/Loading Week 1/i)).toBeInTheDocument();
    });

    // Resolve the promise
    resolveMatchups({ data: [] });

    // Wait for loading to disappear
    await waitFor(() => {
      expect(screen.queryByText(/Loading Week 1/i)).not.toBeInTheDocument();
    });
  });

  test('links to GameCenter for each matchup', async () => {
    const mockGames = [
      {
        id: 99,
        week: 1,
        home_team: 'Team A',
        away_team: 'Team B',
        home_score: 110,
        away_score: 95,
        home_projected: 120,
        away_projected: 100,
      },
    ];

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { username: 'alice', league_id: 1 },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/matchups/week/1') {
        return Promise.resolve({ data: mockGames });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Matchups />);

    await waitFor(() => {
      expect(screen.getByText('Team A')).toBeInTheDocument();
    });

    const gameLink = screen.getByText(/Game Center/i).closest('a');
    expect(gameLink).toHaveAttribute('href', '/matchup/99');
  });
});
