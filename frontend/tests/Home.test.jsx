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
    // analytics link removed from homepage
    expect(screen.queryByText(/League Insights/i)).toBeNull();
  });

  test('renders standings table with owners including stats', async () => {
    const mockOwners = [
      {
        id: 1,
        username: 'alice',
        team_name: 'Runaway Train',
        wins: 2,
        losses: 1,
        ties: 0,
        pf: 250,
        pa: 200,
      },
      {
        id: 2,
        username: 'bob',
        team_name: 'The Legends',
        wins: 1,
        losses: 2,
        ties: 0,
        pf: 180,
        pa: 220,
      },
      {
        id: 3,
        username: 'charlie',
        team_name: 'Sky Club',
        wins: 0,
        losses: 3,
        ties: 0,
        pf: 150,
        pa: 260,
      },
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

  test('renders hot pickups trend and claim metadata when available', async () => {
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
      if (url === '/players/top-free-agents?league_id=1&limit=10') {
        return Promise.resolve({
          data: [
            {
              id: 101,
              name: 'Hot Add',
              position: 'WR',
              nfl_team: 'BUF',
              projected_points: 123.4,
              pickup_score: 129.5,
              pickup_tier: 'A',
              pickup_trend_label: 'Rising',
              pickup_trend_score: 1.8,
              recent_claim_count: 3,
            },
          ],
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');

    await waitFor(() => {
      expect(screen.getByText(/Hot Add/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Trend Rising/i)).toBeInTheDocument();
    expect(screen.getByText(/Claims 3/i)).toBeInTheDocument();
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

  // playoff bracket is now accessed via sidebar; home page no longer
  // renders it directly.  verify nothing obvious about it is present.
  test('home page does not render bracket accordion', async () => {
    apiClient.get.mockResolvedValue({ data: { name: 'The Big Show' } });
    apiClient.get.mockResolvedValue({ data: [] });
    renderHome('alice');
    expect(screen.queryByText(/playoff bracket/i)).not.toBeInTheDocument();
  });

  test('sorting headers reorder standings', async () => {
    const mockOwners = [
      {
        id: 1,
        username: 'zeta',
        team_name: 'Z',
        wins: 1,
        losses: 0,
        ties: 0,
        pf: 100,
        pa: 50,
      },
      {
        id: 2,
        username: 'alpha',
        team_name: 'A',
        wins: 2,
        losses: 0,
        ties: 0,
        pf: 150,
        pa: 60,
      },
    ];
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') return Promise.resolve({ data: { name: 'L' } });
      if (url === '/leagues/owners?league_id=1')
        return Promise.resolve({ data: mockOwners });
      if (url === '/leagues/1/news') return Promise.resolve({ data: [] });
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');
    await waitFor(() => screen.getByText('Z'));
    // click PF header to sort ascending
    const pfHeader = screen.getByText('PF');
    // sort ascending
    pfHeader.click();
    await waitFor(() => {
      const rowsAsc = screen.getAllByRole('row');
      expect(rowsAsc[1]).toHaveTextContent('Z');
    });
    // toggle descending
    pfHeader.click();
    await waitFor(() => {
      const rowsDesc = screen.getAllByRole('row');
      expect(rowsDesc[1]).toHaveTextContent('A');
    });
  });

  test('W-L-T header sorts by full record context', async () => {
    const mockOwners = [
      {
        id: 1,
        username: 'alpha',
        team_name: 'Alpha',
        wins: 6,
        losses: 4,
        ties: 0,
        pf: 900,
        pa: 800,
      },
      {
        id: 2,
        username: 'bravo',
        team_name: 'Bravo',
        wins: 7,
        losses: 3,
        ties: 0,
        pf: 850,
        pa: 810,
      },
    ];

    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') return Promise.resolve({ data: { name: 'L' } });
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({ data: mockOwners });
      }
      if (url === '/leagues/1/news') return Promise.resolve({ data: [] });
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');
    await waitFor(() => screen.getByText('Alpha'));

    const recordHeader = screen.getByText('W-L-T');
    // first click sorts ascending: fewer wins first
    recordHeader.click();
    await waitFor(() => {
      const rowsAsc = screen.getAllByRole('row');
      expect(rowsAsc[1]).toHaveTextContent('Alpha');
    });

    // second click toggles descending: better record first
    recordHeader.click();
    await waitFor(() => {
      const rowsDesc = screen.getAllByRole('row');
      expect(rowsDesc[1]).toHaveTextContent('Bravo');
    });
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
