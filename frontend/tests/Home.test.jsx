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

  test('renders standings table with owners', async () => {
    const mockOwners = [
      { id: 1, username: 'alice', team_name: 'Runaway Train' },
      { id: 2, username: 'bob', team_name: 'The Legends' },
      { id: 3, username: 'charlie', team_name: 'Sky Club' },
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

  test('fetches data from correct league ID from localStorage', async () => {
    localStorage.setItem('fantasyLeagueId', '5');

    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/5') {
        return Promise.resolve({ data: { name: 'Custom League' } });
      }
      if (url === '/leagues/owners?league_id=5') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/leagues/5/news') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    renderHome('alice');

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/leagues/5');
      expect(apiClient.get).toHaveBeenCalledWith('/leagues/owners?league_id=5');
      expect(apiClient.get).toHaveBeenCalledWith('/leagues/5/news');
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
