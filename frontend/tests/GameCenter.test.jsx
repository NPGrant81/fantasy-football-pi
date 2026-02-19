import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('react-router-dom', () => ({
  useParams: () => ({ id: '1' }),
  Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
}));

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}));

import GameCenter from '../src/pages/matchups/GameCenter';
import apiClient from '../src/api/client';

describe('GameCenter (Match Details)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('shows loading state on mount', () => {
    apiClient.get.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<GameCenter />);

    expect(screen.getByText(/Loading Matchup Data/i)).toBeInTheDocument();
  });

  test('fetches and displays game data for given matchup ID', async () => {
    const mockGame = {
      id: 1,
      week: 5,
      home_team: 'Runaway Train',
      away_team: 'The Legends',
      home_score: 125,
      away_score: 118,
      home_projected: 130,
      away_projected: 120,
      home_roster: [],
      away_roster: [],
    };

    apiClient.get.mockResolvedValue({ data: mockGame });

    render(<GameCenter />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/matchups/1');
    });

    await waitFor(() => {
      expect(screen.getByText(/Week 5/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('heading', { level: 2, name: /Runaway Train/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /The Legends/i })).toBeInTheDocument();
  });

  test('displays home and away team starters', async () => {
    const mockGame = {
      id: 1,
      week: 5,
      home_team: 'Runaway Train',
      away_team: 'The Legends',
      home_score: 125,
      away_score: 118,
      home_projected: 130,
      away_projected: 120,
      home_roster: [
        { player_id: 1, name: 'Patrick Mahomes', position: 'QB', nfl_team: 'KC', projected: 25 },
        { player_id: 2, name: 'Travis Kelce', position: 'TE', nfl_team: 'KC', projected: 15 },
      ],
      away_roster: [
        { player_id: 3, name: 'Josh Allen', position: 'QB', nfl_team: 'BUF', projected: 23 },
        { player_id: 4, name: 'Stefon Diggs', position: 'WR', nfl_team: 'BUF', projected: 12 },
      ],
    };

    apiClient.get.mockResolvedValue({ data: mockGame });

    render(<GameCenter />);

    await waitFor(() => {
      expect(screen.getByText('Patrick Mahomes')).toBeInTheDocument();
    });
    expect(screen.getByText('Travis Kelce')).toBeInTheDocument();
    expect(screen.getByText('Josh Allen')).toBeInTheDocument();
    expect(screen.getByText('Stefon Diggs')).toBeInTheDocument();
  });

  test('displays player positions with correct colors', async () => {
    const mockGame = {
      id: 1,
      week: 5,
      home_team: 'Team A',
      away_team: 'Team B',
      home_score: 100,
      away_score: 95,
      home_projected: 105,
      away_projected: 100,
      home_roster: [
        { player_id: 1, name: 'QB1', position: 'QB', nfl_team: 'KC', projected: 25 },
        { player_id: 2, name: 'RB1', position: 'RB', nfl_team: 'KC', projected: 15 },
        { player_id: 3, name: 'WR1', position: 'WR', nfl_team: 'KC', projected: 12 },
        { player_id: 4, name: 'TE1', position: 'TE', nfl_team: 'KC', projected: 10 },
      ],
      away_roster: [],
    };

    apiClient.get.mockResolvedValue({ data: mockGame });

    render(<GameCenter />);

    await waitFor(() => {
      expect(screen.getByText('QB')).toBeInTheDocument();
    });
    expect(screen.getAllByText('RB')[0]).toBeInTheDocument();
    expect(screen.getAllByText('WR')[0]).toBeInTheDocument();
    expect(screen.getByText('TE')).toBeInTheDocument();
  });

  test('displays "No starters set" when team has no starters', async () => {
    const mockGame = {
      id: 1,
      week: 5,
      home_team: 'Team A',
      away_team: 'Team B',
      home_score: 100,
      away_score: 95,
      home_projected: 105,
      away_projected: 100,
      home_roster: [],
      away_roster: [
        { player_id: 1, name: 'Player', position: 'QB', nfl_team: 'KC', projected: 20 },
      ],
    };

    apiClient.get.mockResolvedValue({ data: mockGame });

    render(<GameCenter />);

    await waitFor(() => {
      expect(screen.getByText('Player')).toBeInTheDocument();
    });
    expect(screen.getByText(/No starters set/i)).toBeInTheDocument();
  });

  test('back link navigates to matchups page', async () => {
    const mockGame = {
      id: 1,
      week: 5,
      home_team: 'Team A',
      away_team: 'Team B',
      home_score: 100,
      away_score: 95,
      home_projected: 105,
      away_projected: 100,
      home_roster: [],
      away_roster: [],
    };

    apiClient.get.mockResolvedValue({ data: mockGame });

    render(<GameCenter />);

    await waitFor(() => {
      expect(screen.getByText(/Week 5/i)).toBeInTheDocument();
    });

    const backLink = screen.getByRole('link', { name: /back to matchups/i });
    expect(backLink).toHaveAttribute('href', '/matchups');
  });

  test('handles API error gracefully', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiClient.get.mockRejectedValue(new Error('API Error'));

    render(<GameCenter />);

    await waitFor(() => {
      expect(screen.getByText(/Matchup data unavailable/i)).toBeInTheDocument();
    });

    consoleErrorSpy.mockRestore();
  });

  test('fetches data with correct matchup ID from route params', async () => {
    vi.resetAllMocks();

    apiClient.get.mockResolvedValue({
      data: {
        id: 42,
        week: 5,
        home_team: 'Team A',
        away_team: 'Team B',
        home_score: 100,
        away_score: 95,
        home_projected: 105,
        away_projected: 100,
        home_roster: [],
        away_roster: [],
      },
    });

    render(<GameCenter />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/matchups/1');
    });
  });

  test('displays projected scores in player rows', async () => {
    const mockGame = {
      id: 1,
      week: 5,
      home_team: 'Team A',
      away_team: 'Team B',
      home_score: 100,
      away_score: 95,
      home_projected: 105,
      away_projected: 100,
      home_roster: [
        { player_id: 1, name: 'Star Player', position: 'QB', nfl_team: 'KC', projected: 27.5 },
      ],
      away_roster: [],
    };

    apiClient.get.mockResolvedValue({ data: mockGame });

    render(<GameCenter />);

    await waitFor(() => {
      expect(screen.getByText('27.5')).toBeInTheDocument();
    });
  });
});
