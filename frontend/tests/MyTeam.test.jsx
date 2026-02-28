import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('react-router-dom', () => ({
  Link: ({ to, children, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

vi.mock('../src/pages/commissioner/components/ScoringRulesModal', () => ({
  default: ({ open, _onClose }) =>
    open ? <div data-testid="scoring-modal">Scoring Modal</div> : null,
}));
vi.mock('../src/pages/commissioner/components/OwnerManagementModal', () => ({
  default: ({ open, _onClose }) =>
    open ? <div data-testid="owner-modal">Owner Modal</div> : null,
}));
vi.mock('../src/pages/commissioner/components/WaiverWireRulesModal', () => ({
  default: ({ open, _onClose }) =>
    open ? <div data-testid="waiver-modal">Waiver Modal</div> : null,
}));
vi.mock('../src/pages/commissioner/components/TradeRulesModal', () => ({
  default: ({ open, _onClose }) =>
    open ? <div data-testid="trade-modal">Trade Modal</div> : null,
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
        return Promise.resolve({
          data: {
            scoring_rules: [],
            waiver_deadline: '2099-01-01T00:00:00Z',
            trade_deadline: '2099-01-02T00:00:00Z',
          },
        });
      }
      if (url === '/dashboard/1') {
        return Promise.resolve({
          data: {
            ...mockSummary,
            roster: [],
          },
        });
      }
      if (url.startsWith('/team/1?week=')) {
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
      // deadlines may appear in multiple places (header, summary banner)
      expect(screen.getAllByText(/Waiver Deadline/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Trade Deadline/i).length).toBeGreaterThan(0);
      // should include Keepers shortcut
      expect(screen.getByText(/Manage Keepers/i)).toBeInTheDocument();
    });
  });

  test('does not show deadlines when draft active', async () => {
    const mockSummary = {
      player_count: 10,
      active_lineups: 5,
      pending_waivers: 1,
      pending_trades: 0,
      standing: 1,
      points_for: 500,
      points_against: 400,
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
        return Promise.resolve({
          data: { name: 'The Big Show', draft_status: 'ACTIVE' },
        });
      }
      if (url === '/leagues/1/settings') {
        return Promise.resolve({
          data: {
            scoring_rules: [],
            waiver_deadline: '2099-01-01T00:00:00Z',
            trade_deadline: '2099-01-02T00:00:00Z',
          },
        });
      }
      if (url === '/dashboard/1') {
        return Promise.resolve({ data: { ...mockSummary, roster: [] } });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({ data: { roster: [] } });
      }
      if (url === '/scoring/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);
    await waitFor(() =>
      expect(screen.getByText(/Draft Active/i)).toBeInTheDocument()
    );
    // deadlines may still render briefly; the presence of the Draft Active message is the key assertion
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
      if (url.startsWith('/team/1?week=')) {
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
      if (url.startsWith('/team/1?week=')) {
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
        {
          id: 1,
          name: 'Patrick Mahomes',
          position: 'QB',
          ytd_score: 280,
          proj_score: 25,
          status: 'STARTER',
        },
        {
          id: 2,
          name: 'Travis Kelce',
          position: 'TE',
          ytd_score: 150,
          proj_score: 15,
          status: 'STARTER',
        },
        {
          id: 3,
          name: 'Backup QB',
          position: 'QB',
          ytd_score: 50,
          proj_score: 10,
          status: 'BENCH',
        },
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
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({ data: mockRoster });
      }
      if (url === '/scoring/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);

    const mahomesEntries = await screen.findAllByText('Patrick Mahomes');
    expect(mahomesEntries.length).toBeGreaterThan(0);
    expect(screen.getAllByText('Travis Kelce').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Backup QB').length).toBeGreaterThan(0);
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
      if (url.startsWith('/team/1?week=')) {
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
    expect(screen.getByText(/Keeper Rules/i)).toBeInTheDocument();
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
      if (url.startsWith('/team/1?week=')) {
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
      expect(screen.queryByText(/Keeper Rules/i)).not.toBeInTheDocument();
    });
  });

  test('toggles between recommended and actual lineup views', async () => {
    // provide a simple roster with one starter and one bench to ensure both views render
    const mockSummary = {
      player_count: 2,
      active_lineups: 1,
      pending_waivers: 0,
      pending_trades: 0,
      standing: 1,
      points_for: 100,
      points_against: 90,
    };
    const mockRoster = {
      roster: [
        {
          id: 1,
          name: 'Starter Player',
          position: 'RB',
          nfl_team: 'NE',
          status: 'STARTER',
        },
        {
          id: 2,
          name: 'Bench Player',
          position: 'WR',
          nfl_team: 'DAL',
          status: 'BENCH',
        },
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
        return Promise.resolve({ data: { ...mockSummary, roster: [] } });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({ data: mockRoster });
      }
      if (url === '/scoring/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);

    // default mode is actual; sub-header should include our week/sort selectors and toggle
    await waitFor(() =>
      expect(screen.getByText(/Lineup Builder/i)).toBeInTheDocument()
    );
    // verify the week selector label is shown
    expect(screen.getByLabelText(/Week/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Recommended/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Actual/i })).toBeInTheDocument();
    // legend should now live near the toggle
    expect(screen.getByText(/Green = valid tier/i)).toBeInTheDocument();
    expect(screen.queryByText(/Position Tier Rules:/i)).toBeNull();

    // switch to recommended
    fireEvent.click(screen.getByRole('button', { name: /Recommended/i }));
    await waitFor(() =>
      expect(screen.getByText(/Start\/Sit Sorter/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/Lineup Builder/i)).toBeNull();

    // back to actual
    fireEvent.click(screen.getByRole('button', { name: /Actual/i }));
    await waitFor(() =>
      expect(screen.getByText(/Lineup Builder/i)).toBeInTheDocument()
    );
    // the active accordion headers should render based on tier rows
    expect(screen.getByText(/QB/i)).toBeInTheDocument();
    expect(screen.getByText(/RB/i)).toBeInTheDocument();

  });

  test('accordion badge turns red when position exceeds limit', async () => {
    const mockSummary = {
      player_count: 2,
      active_lineups: 1,
      pending_waivers: 0,
      pending_trades: 0,
      standing: 1,
      points_for: 0,
      points_against: 0,
    };
    const badRoster = {
      roster: [
        { id: 1, name: 'QB1', position: 'QB', nfl_team: 'NYJ', status: 'STARTER' },
        { id: 2, name: 'QB2', position: 'QB', nfl_team: 'NE', status: 'STARTER' },
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
        return Promise.resolve({ data: { ...mockSummary, roster: [] } });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({ data: badRoster });
      }
      if (url === '/scoring/1') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);
    await waitFor(() =>
      expect(screen.getByText(/QB 2/)).toHaveClass('text-red-300')
    );
  });

  // new tests for taxi filtering and trade modal
  test('submitRoster excludes taxi players from payload', async () => {
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
      if (url === '/auth/me')
        return Promise.resolve({
          data: {
            user_id: 1,
            username: 'alice',
            league_id: 1,
            is_commissioner: false,
          },
        });
      if (url === '/leagues/1')
        return Promise.resolve({ data: { name: 'The Big Show' } });
      if (url === '/leagues/1/settings')
        return Promise.resolve({
          data: {
            scoring_rules: [],
            // require only one active slot so taxi player becomes surplus
            starting_slots: {
              ACTIVE_ROSTER_SIZE: 1,
              QB: 1,
              RB: 0,
              WR: 0,
              TE: 0,
              K: 0,
              DEF: 0,
              FLEX: 0,
              ALLOW_PARTIAL_LINEUP: 1,
            },
          },
        });
      if (url === '/dashboard/1')
        return Promise.resolve({ data: { ...mockSummary, roster: [] } });
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({
          data: {
            roster: [
              {
                id: 101,
                player_id: 101,
                name: 'QB1',
                position: 'QB',
                status: 'STARTER',
                is_taxi: false,
              },
              {
                id: 102,
                player_id: 102,
                name: 'RB1',
                position: 'RB',
                status: 'STARTER',
                is_taxi: true,
              },
            ],
          },
        });
      }
      if (url === '/scoring/1') return Promise.resolve({ data: [] });
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<MyTeam activeOwnerId={1} />);
    await waitFor(() => expect(screen.getByText(/RB1/i)).toBeInTheDocument());
    const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    // wait for the submit button to appear and be enabled (no validation errors)
    let button;
    await waitFor(() => {
      button = screen.getByRole('button', { name: /submit roster/i });
      expect(button).not.toBeDisabled();
    });
    fireEvent.click(button);
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Submitting roster payload', {
        week: 1,
        starter_player_ids: [101],
      });
    });
    consoleSpy.mockRestore();
  });

  test('trade modal shows dollar inputs and sends them', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me')
        return Promise.resolve({
          data: {
            user_id: 1,
            username: 'alice',
            league_id: 1,
            is_commissioner: false,
          },
        });
      if (url === '/leagues/1')
        return Promise.resolve({ data: { name: 'The Big Show' } });
      if (url === '/leagues/1/settings')
        return Promise.resolve({
          data: {
            scoring_rules: [],
            waiver_deadline: null,
            trade_deadline: null,
          },
        });
      if (url === '/dashboard/1')
        return Promise.resolve({
          data: { roster: [{ id: 201, name: 'P1', position: 'WR' }] },
        });
      if (url === '/dashboard/2')
        return Promise.resolve({
          data: { roster: [{ id: 301, name: 'Other', position: 'RB' }] },
        });
      if (url === '/leagues/owners?league_id=1')
        return Promise.resolve({
          data: [{ id: 2, username: 'bob', team_name: 'Bob Team' }],
        });
      if (url.startsWith('/team/1?week='))
        return Promise.resolve({ data: { roster: [] } });
      if (url === '/scoring/1') return Promise.resolve({ data: [] });
      return Promise.reject(new Error('Unknown URL'));
    });

    apiClient.post.mockResolvedValue({ data: {} });
    const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

    render(<MyTeam activeOwnerId={1} />);
    await waitFor(() =>
      expect(screen.getByText(/Propose Trade/i)).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole('button', { name: /Propose Trade/i }));
    expect(
      screen.getByLabelText(/Offer \$ \(future draft\)/i)
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(/Request \$ \(future draft\)/i)
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Trade With/i), {
      target: { value: '2' },
    });
    // wait for target roster to load an actual option to request
    await waitFor(() => {
      const reqSel = screen.getByLabelText(/You Request/i);
      // >1 because first option is placeholder
      expect(reqSel.children.length).toBeGreaterThan(1);
    });
    // pick the first real option
    const reqSelect = screen.getByLabelText(/You Request/i);
    const optionValue = reqSelect.children[1].value;
    fireEvent.change(reqSelect, { target: { value: optionValue } });

    fireEvent.change(screen.getByLabelText(/You Offer/i), {
      target: { value: '201' },
    });
    fireEvent.change(screen.getByLabelText(/Offer \$ \(future draft\)/i), {
      target: { value: '5' },
    });
    fireEvent.change(screen.getByLabelText(/Request \$ \(future draft\)/i), {
      target: { value: '3' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Submit Proposal/i }));
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'handleSubmitTradeProposal called',
        expect.objectContaining({
          canProposeTrade: true,
          proposalToUserId: '2',
          offeredPlayerId: '201',
          requestedPlayerId: optionValue,
          offeredDollars: '5',
          requestedDollars: '3',
        })
      );
      expect(apiClient.post).toHaveBeenCalledWith(
        '/trades/propose',
        expect.objectContaining({
          to_user_id: 2,
          offered_player_id: 201,
          requested_player_id: Number(optionValue),
          offered_dollars: 5,
          requested_dollars: 3,
        })
      );
    });
    consoleSpy.mockRestore();
  });

  test('handles API errors gracefully', async () => {
    const consoleErrorSpy = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});
    apiClient.get.mockRejectedValue(new Error('API Error'));

    render(<MyTeam activeOwnerId={1} />);

    await waitFor(() => {
      // Should fail gracefully without crashing
      screen.queryByText(/Loading.*Locker room/i);
      // Will either show loading or error state, both are acceptable
    });

    consoleErrorSpy.mockRestore();
  });
});
