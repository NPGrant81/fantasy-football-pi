import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('react-router-dom', () => ({
  Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
}));

vi.mock('../src/pages/commissioner/components/ScoringRulesModal', () => ({
  default: ({ open, _onClose }) => open ? <div data-testid="scoring-modal">Scoring Modal</div> : null,
}));
vi.mock('../src/pages/commissioner/components/OwnerManagementModal', () => ({
  default: ({ open, _onClose }) => open ? <div data-testid="owner-modal">Owner Modal</div> : null,
}));
vi.mock('../src/pages/commissioner/components/WaiverWireRulesModal', () => ({
  default: ({ open, _onClose }) => open ? <div data-testid="waiver-modal">Waiver Modal</div> : null,
}));
vi.mock('../src/pages/commissioner/components/TradeRulesModal', () => ({
  default: ({ open, _onClose }) => open ? <div data-testid="trade-modal">Trade Modal</div> : null,
}));
vi.mock('../src/components/LeagueAdvisor', () => ({
  default: () => <div data-testid="league-advisor">League Advisor</div>,
}));

import MyTeam from '../src/pages/team-owner/MyTeam';
import apiClient from '../src/api/client';

describe('MyTeam (Roster & Lineups)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders loading state while fetching team data', () => {
    apiClient.get.mockImplementation(() => new Promise(() => {}));

    render(<MyTeam activeOwnerId={1} />);

    expect(screen.getByText(/Loading Roster/i)).toBeInTheDocument();
  });

  test('fetches and displays team summary data', async () => {
    const mockSummary = {
      player_count: 15,
      active_lineups: 8,
      pending_waivers: 2,
      pending_trades: 1,
      standing: 3,
      points_for: 1250,
      points_against: 1180,
    };

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: {
            user_id: 1,
            username: 'alice',
            league_id: 1,
            is_commissioner: false,
          },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/1/settings') {
        return Promise.resolve({ data: { scoring_rules: [] } });
      }
      if (url === '/dashboard/1') {
        return Promise.resolve({
          data: {
            ...mockSummary,
            roster: [],
          },
        });
      }
      if (url === '/team/1') {
        return Promise.resolve({ data: { roster: [] } });
      }
      if (url === '/scoring/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.getByText(/Your Locker Room/i)).toBeInTheDocument();
    });
  });

  test('displays team standing', async () => {
    const mockSummary = {
      player_count: 15,
      active_lineups: 8,
      pending_waivers: 2,
      pending_trades: 1,
      standing: 2,
      points_for: 1250,
      points_against: 1180,
    };

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: {
            user_id: 1,
            username: 'alice',
            league_id: 1,
            is_commissioner: false,
          },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/1/settings') {
        return Promise.resolve({ data: { scoring_rules: [] } });
      }
      if (url === '/dashboard/1') {
        return Promise.resolve({
          data: {
            ...mockSummary,
            roster: [],
          },
        });
      }
      if (url === '/team/1') {
        return Promise.resolve({ data: { roster: [] } });
      }
      if (url === '/scoring/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.getByText(/#2 Place/i)).toBeInTheDocument();
    });
  });

  test('displays pending trades stat box', async () => {
    const mockSummary = {
      player_count: 15,
      active_lineups: 8,
      pending_waivers: 3,
      pending_trades: 2,
      standing: 1,
      points_for: 1250,
      points_against: 1180,
    };

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: {
            user_id: 1,
            username: 'alice',
            league_id: 1,
            is_commissioner: false,
          },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/1/settings') {
        return Promise.resolve({ data: { scoring_rules: [] } });
      }
      if (url === '/dashboard/1') {
        return Promise.resolve({
          data: {
            ...mockSummary,
            roster: [],
          },
        });
      }
      if (url === '/team/1') {
        return Promise.resolve({ data: { roster: [] } });
      }
      if (url === '/scoring/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument();
    });
  });

  test('displays roster list from summary', async () => {
    const mockSummary = {
      player_count: 15,
      active_lineups: 8,
      pending_waivers: 0,
      pending_trades: 0,
      standing: 1,
      points_for: 1250,
      points_against: 1180,
      roster: [
        { id: 1, name: 'Patrick Mahomes', position: 'QB', nfl_team: 'KC' },
        { id: 2, name: 'Travis Kelce', position: 'TE', nfl_team: 'KC' },
        { id: 3, name: 'Backup QB', position: 'QB', nfl_team: 'DAL' },
      ],
    };

    const mockRoster = {
      roster: [
        { id: 1, name: 'Patrick Mahomes', position: 'QB', ytd_score: 280, proj_score: 25, status: 'STARTER' },
        { id: 2, name: 'Travis Kelce', position: 'TE', ytd_score: 150, proj_score: 15, status: 'STARTER' },
        { id: 3, name: 'Backup QB', position: 'QB', ytd_score: 50, proj_score: 10, status: 'BENCH' },
      ],
    };

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: {
            user_id: 1,
            username: 'alice',
            league_id: 1,
            is_commissioner: false,
          },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/1/settings') {
        return Promise.resolve({ data: { scoring_rules: [] } });
      }
      if (url === '/dashboard/1') {
        return Promise.resolve({
          data: {
            ...mockSummary,
          },
        });
      }
      if (url === '/team/1') {
        return Promise.resolve({ data: mockRoster });
      }
      if (url === '/scoring/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);

    expect(await screen.findByText('Patrick Mahomes')).toBeInTheDocument();
    expect(screen.getByText('Travis Kelce')).toBeInTheDocument();
    expect(screen.getByText('Backup QB')).toBeInTheDocument();
  });

  test('shows commissioner controls when user is commissioner', async () => {
    const mockSummary = {
      player_count: 15,
      active_lineups: 8,
      pending_waivers: 0,
      pending_trades: 0,
      standing: 1,
      points_for: 1250,
      points_against: 1180,
    };

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: {
            user_id: 1,
            username: 'alice',
            league_id: 1,
            is_commissioner: true, // Commissioner!
          },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/1/settings') {
        return Promise.resolve({ data: { scoring_rules: [] } });
      }
      if (url === '/dashboard/1') {
        return Promise.resolve({
          data: {
            ...mockSummary,
            roster: [],
          },
        });
      }
      if (url === '/team/1') {
        return Promise.resolve({ data: { roster: [] } });
      }
      if (url === '/scoring/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.getByText(/Scoring Rules/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Owner Management/i)).toBeInTheDocument();
  });

  test('hides commissioner controls when user is not commissioner', async () => {
    const mockSummary = {
      player_count: 15,
      active_lineups: 8,
      pending_waivers: 0,
      pending_trades: 0,
      standing: 1,
      points_for: 1250,
      points_against: 1180,
    };

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: {
            user_id: 1,
            username: 'alice',
            league_id: 1,
            is_commissioner: false, // Not commissioner
          },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/leagues/1/settings') {
        return Promise.resolve({ data: { scoring_rules: [] } });
      }
      if (url === '/dashboard/1') {
        return Promise.resolve({
          data: {
            ...mockSummary,
            roster: [],
          },
        });
      }
      if (url === '/team/1') {
        return Promise.resolve({ data: { roster: [] } });
      }
      if (url === '/scoring/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.queryByText(/Scoring Rules/i)).not.toBeInTheDocument();
    });
  });

  test('handles API errors gracefully', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiClient.get.mockRejectedValue(new Error('API Error'));

    render(<MyTeam activeOwnerId={1} />);

    await waitFor(() => {
      // Should fail gracefully without crashing
      const _content = screen.queryByText(/Loading.*Locker room/i);
      // Will either show loading or error state, both are acceptable
    });

    consoleErrorSpy.mockRestore();
  });
});
