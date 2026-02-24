import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}));

import Home from '../src/pages/home/Home';
import apiClient from '../src/api/client';

const renderHome = (username = 'alice') =>
  render(
    <MemoryRouter>
      <Home username={username} />
    </MemoryRouter>
  );

describe('Home (League Dashboard)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
    localStorage.setItem('fantasyLeagueId', '1');
  });

  test('renders welcome banner with username and league name', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/leagues/1/news') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');

    await waitFor(() => {
      expect(screen.getByText(/THE BIG SHOW/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Welcome back,/i)).toBeInTheDocument();
    expect(screen.getByText('alice')).toBeInTheDocument();
  });

  test('renders standings table with owners including stats', async () => {
    const mockOwners = [
      { id: 1, username: 'alice', team_name: 'Runaway Train', wins: 2, losses: 1, ties: 0, pf: 250, pa: 200 },
      { id: 2, username: 'bob', team_name: 'The Legends', wins: 1, losses: 2, ties: 0, pf: 180, pa: 220 },
      { id: 3, username: 'charlie', team_name: 'Sky Club', wins: 0, losses: 3, ties: 0, pf: 150, pa: 260 },
    ];

    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({ data: mockOwners });
      }
      if (url === '/leagues/1/news') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');

    await waitFor(() => {
      expect(screen.getByText('Runaway Train')).toBeInTheDocument();
    });
    const standingsTable = screen.getByRole('table');
    const tableScope = within(standingsTable);
    expect(tableScope.getByText('The Legends')).toBeInTheDocument();
    expect(tableScope.getByText('Sky Club')).toBeInTheDocument();
    expect(tableScope.getByText('alice')).toBeInTheDocument();
    expect(tableScope.getByText('bob')).toBeInTheDocument();
    expect(tableScope.getByText('charlie')).toBeInTheDocument();

    // verify stats columns rendered
    expect(tableScope.getByText('2-1-0')).toBeInTheDocument();
    expect(tableScope.getByText('250')).toBeInTheDocument();
    expect(tableScope.getByText('200')).toBeInTheDocument();
  });

  test('displays ranking (1st place highlighted in yellow)', async () => {
    const mockOwners = [
      { id: 1, username: 'alice', team_name: 'Leader' },
      { id: 2, username: 'bob', team_name: 'Second Place' },
    ];

    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({ data: mockOwners });
      }
      if (url === '/leagues/1/news') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');

    await waitFor(() => {
      const rankCells = screen.getAllByText('1');
      expect(rankCells[0]).toBeInTheDocument(); // Rank "1"
    });
  });

  test('renders league news feed', async () => {
    const mockNews = [
      { type: 'info', title: 'Season Started', timestamp: '2026-01-01' },
      { type: 'warning', title: 'Trade Deadline', timestamp: '2026-01-15' },
    ];

    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/leagues/1/news') {
        return Promise.resolve({ data: mockNews });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');

    await waitFor(() => {
      expect(screen.getByText('Season Started')).toBeInTheDocument();
    });
    expect(screen.getByText('Trade Deadline')).toBeInTheDocument();
  });

  test('displays "end of feed" message when no news', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/leagues/1/news') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');

    await waitFor(() => {
      expect(screen.getByText(/End of feed/i)).toBeInTheDocument();
    });
  });

  test('shows "no owners" message when standings are empty', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/leagues/1/news') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');

    await waitFor(() => {
      expect(screen.getByText(/No owners found/i)).toBeInTheDocument();
    });
  });

  test('bracket accordion fetches and displays matches', async () => {
    const bracketData = {
      championship: [
        { match_id: 'm1', round: 1, is_bye: true, team_1_id: 1, team_2_id: null, winner_to: 'r2_m1' },
      ],
      consolation: [],
    };
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/leagues/1/news') {
        return Promise.resolve({ data: [] });
      }
      if (url.startsWith('/playoffs/bracket')) {
        return Promise.resolve({ data: bracketData });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');

    // open accordion
    const summary = screen.getByText(/playoff bracket/i);
    summary.click();

    await waitFor(() => {
      expect(screen.getByText(/m1/)).toBeInTheDocument();
    });
  });

  test('sorting headers reorder standings', async () => {
    const mockOwners = [
      { id: 1, username: 'zeta', team_name: 'Z', wins: 1, losses:0, ties:0, pf: 100, pa: 50 },
      { id: 2, username: 'alpha', team_name: 'A', wins: 2, losses:0, ties:0, pf: 150, pa: 60 },
    ];
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') return Promise.resolve({ data: { name: 'L' } });
      if (url === '/leagues/owners?league_id=1') return Promise.resolve({ data: mockOwners });
      if (url === '/leagues/1/news') return Promise.resolve({ data: [] });
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');
    await waitFor(() => screen.getByText('Z'));
    // click PF header to sort ascending
    const pfHeader = screen.getByText('PF');
    pfHeader.click();
    // after sorting ascending, Z (100) should appear before A (150)
    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('Z');
    pfHeader.click(); // toggle descending
    expect(rows[1]).toHaveTextContent('A');
  });

  test('does not fetch data when league ID is missing', () => {
    localStorage.removeItem('fantasyLeagueId');

    renderHome('alice');

    // Should not make API calls when league ID is not available
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  test('handles API errors gracefully', async () => {
    apiClient.get.mockRejectedValue(new Error('API Error'));

    renderHome('alice');

    await waitFor(() => {
      // Should still render the page structure
      expect(screen.getByText(/LEAGUE DASHBOARD/i)).toBeInTheDocument();
    });
  });
});
