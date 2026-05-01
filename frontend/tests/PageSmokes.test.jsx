import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
  mockNavigate,
} from '../src/setupTests';
import { vi } from 'vitest';

// setupTests.js now provides global mocks for apiClient and react-router-dom.
// individual tests only need to configure the mock implementations.  the
// global setup also automagically wraps renders with a MemoryRouter so no
// further boilerplate is required.
import apiClient from '@/api/client';
import DraftBoard from '@/pages/DraftBoard';
import DraftDayAnalyzer from '@/pages/DraftDayAnalyzer';
import WaiverWire from '@/pages/WaiverWire';
import WaiverRules from '@/pages/WaiverRules';
import ManageWaiverRules from '@/pages/commissioner/ManageWaiverRules';
import ManageKeeperRules from '@/pages/commissioner/ManageKeeperRules';
import SiteAdmin from '@/pages/admin/SiteAdmin';
import CommissionerDashboard from '@/pages/commissioner/CommissionerDashboard';
import ManageTrades from '@/pages/commissioner/ManageTrades';
import CommishAdmin from '@/pages/commissioner/CommishAdmin';
import MyTeam from '@/pages/team-owner/YourLockerRoom';
import TradeAnalyzer from '@/components/charts/TradeAnalyzer';

describe('DraftBoard (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders without crashing', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/owners'))
        return Promise.resolve({ data: [] });
      if (url === '/players/') return Promise.resolve({ data: [] });
      if (url.startsWith('/draft/history'))
        return Promise.resolve({ data: [] });
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { draft_year: 2026 } });
      }
      if (url.startsWith('/leagues/1/budgets'))
        return Promise.resolve({ data: [] });
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { is_commissioner: false, username: 'alice' },
        });
      }
      if (url === '/leagues/1')
        return Promise.resolve({ data: { name: 'The Big Show' } });
      return Promise.resolve({ data: [] });
    });
    apiClient.post.mockResolvedValue({ data: {} });

    const { container } = render(
      <DraftBoard token="test-token" activeOwnerId={1} activeLeagueId={1} />
    );

    await waitFor(() => {
      expect(container).toBeInTheDocument();
      expect(screen.getByText(/Nominating Team|Nominator/i)).toBeInTheDocument();
    });
  });

  test('ManageKeeperRules renders without crashing', async () => {
    // reuse the same mocks above
    render(<ManageKeeperRules />);
    await waitFor(() => {
      expect(screen.getByText(/Keeper Rules/i)).toBeInTheDocument();
    });
  });

  test('shows pause button for commissioner', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/owners'))
        return Promise.resolve({ data: [] });
      if (url === '/players/') return Promise.resolve({ data: [] });
      if (url.startsWith('/draft/history'))
        return Promise.resolve({ data: [] });
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { draft_year: 2026 } });
      }
      if (url.startsWith('/leagues/1/budgets'))
        return Promise.resolve({ data: [] });
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { is_commissioner: true, username: 'admin' },
        });
      }
      if (url === '/leagues/1')
        return Promise.resolve({ data: { name: 'The Big Show' } });
      return Promise.resolve({ data: [] });
    });
    apiClient.post.mockResolvedValue({ data: {} });

    render(
      <DraftBoard token="test-token" activeOwnerId={1} activeLeagueId={1} />
    );

    await waitFor(() => {
      expect(screen.getByText(/Pause/i)).toBeInTheDocument();
      expect(screen.getByText(/End Draft Session/i)).toBeInTheDocument();
    });
  });

  test('renders session metadata when provided', async () => {
    const mockAlert = vi.fn();
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/owners'))
        return Promise.resolve({ data: [] });
      if (url === '/players/') return Promise.resolve({ data: [] });
      if (url.startsWith('/draft/history'))
        return Promise.resolve({ data: [] });
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { draft_year: 2026 } });
      }
      if (url.startsWith('/leagues/1/budgets'))
        return Promise.resolve({ data: [] });
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { is_commissioner: false, username: 'alice' },
        });
      }
      if (url === '/leagues/1')
        return Promise.resolve({ data: { name: 'The Big Show' } });
      return Promise.resolve({ data: [] });
    });
    apiClient.post.mockResolvedValue({ data: {} });

    render(
      <DraftBoard
        token="test-token"
        activeOwnerId={1}
        activeLeagueId={1}
        setSubHeader={mockAlert}
      />
    );

    await waitFor(() => {
      expect(screen.getAllByText(/Session ID:/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/LEAGUE_1_YEAR_2026/i).length).toBeGreaterThan(
        0
      );
    });
  });

  test('handles missing props gracefully', async () => {
    apiClient.get.mockResolvedValue({ data: [] });
    const { container } = render(<DraftBoard />);
    await waitFor(() => {
      expect(container).toBeInTheDocument();
    });
  });

  test('does not render analyzer panels in war room', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/owners'))
        return Promise.resolve({ data: [] });
      if (url === '/players/') return Promise.resolve({ data: [] });
      if (url.startsWith('/draft/history'))
        return Promise.resolve({ data: [] });
      if (url.startsWith('/draft/rankings')) {
        return Promise.resolve({
          data: [
            {
              player_id: 10,
              player_name: 'Ranked Player',
              position: 'WR',
              season: 2026,
              rank: 1,
              predicted_auction_value: 48,
              value_over_replacement: 18,
              consensus_tier: 'S',
            },
          ],
        });
      }
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { draft_year: 2026 } });
      }
      if (url.startsWith('/leagues/1/budgets'))
        return Promise.resolve({ data: [] });
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { is_commissioner: false, username: 'alice' },
        });
      }
      if (url === '/leagues/1')
        return Promise.resolve({ data: { name: 'The Big Show' } });
      return Promise.resolve({ data: [] });
    });

    render(<DraftBoard token="test-token" activeOwnerId={1} activeLeagueId={1} />);

    await waitFor(() => {
      expect(screen.getByText(/Draft Board/i)).toBeInTheDocument();
    });

    expect(screen.queryByText(/Historical Rankings/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Perspective Simulation/i)).not.toBeInTheDocument();
  });

  test('renders analyzer modules on dedicated page', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/owners')) {
        return Promise.resolve({
          data: [
            { id: 1, username: 'alice', team_name: 'Alpha' },
            { id: 2, username: 'bob', team_name: 'Beta' },
          ],
        });
      }
      if (url === '/players/') return Promise.resolve({ data: [] });
      if (url.startsWith('/draft/history')) return Promise.resolve({ data: [] });
      if (url.startsWith('/draft/rankings')) {
        return Promise.resolve({
          data: [
            {
              player_id: 10,
              player_name: 'Ranked Player',
              position: 'WR',
              season: 2026,
              rank: 1,
              predicted_auction_value: 48,
              value_over_replacement: 18,
              consensus_tier: 'S',
            },
          ],
        });
      }
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { draft_year: 2026, roster_size: 16 } });
      }
      if (url.startsWith('/leagues/1/budgets')) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });

    render(<DraftDayAnalyzer activeOwnerId={1} activeLeagueId={1} />);

    await waitFor(() => {
      expect(screen.getByText(/Draft Day Analyzer/i)).toBeInTheDocument();
      expect(screen.getByText(/Analyzer Insights/i)).toBeInTheDocument();
      expect(screen.getByText(/Perspective Simulation/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Run Simulation/i })).toBeInTheDocument();
    });
  });
});

describe('WaiverWire (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders without crashing', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/The Big Show')
        return Promise.resolve({ data: { draft_status: 'PRE_DRAFT' } });
      if (url === '/leagues/The Big Show/settings')
        return Promise.resolve({ data: { waiver_deadline: '2026-09-01' } });
      return Promise.resolve({ data: [] });
    });

    const { container } = render(
      <WaiverWire
        activeOwnerId={1}
        username="alice"
        leagueName="The Big Show"
      />
    );

    await waitFor(() => {
      expect(container).toBeInTheDocument();
    });
  });

  test('shows deadline when provided', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/The Big Show')
        return Promise.resolve({ data: { draft_status: 'PRE_DRAFT' } });
      if (url === '/leagues/The Big Show/settings')
        return Promise.resolve({ data: { waiver_deadline: '2026-09-01' } });
      if (url === '/players/waiver-wire') return Promise.resolve({ data: [] });
      if (url.startsWith('/dashboard/'))
        return Promise.resolve({ data: { roster: [] } });
      return Promise.resolve({ data: [] });
    });

    render(
      <WaiverWire
        activeOwnerId={1}
        username="alice"
        leagueName="The Big Show"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Waiver Deadline/i)).toBeInTheDocument();
      expect(screen.getByText(/View waiver rules/i)).toBeInTheDocument();
    });
  });

  // new WaiverRules tests
  describe('WaiverRules (Smoke Test)', () => {
    beforeEach(() => {
      localStorage.clear();
      vi.resetAllMocks();
    });

    test('renders rules read-only for normal user', async () => {
      apiClient.get.mockImplementation((url) => {
        if (url === '/auth/me')
          return Promise.resolve({ data: { is_commissioner: false } });
        if (url === '/leagues/1/settings')
          return Promise.resolve({
            data: { waiver_deadline: 'D', roster_size: 12 },
          });
        return Promise.resolve({ data: {} });
      });

      const { getByText, queryByText } = render(<WaiverRules leagueId={1} />);
      await waitFor(() => {
        expect(getByText(/Waiver Wire Rules/i)).toBeInTheDocument();
        expect(getByText('Waiver Deadline:', { selector: 'strong' })).toBeInTheDocument();
        expect(getByText(/Starting FAAB Budget/i)).toBeInTheDocument();
        expect(getByText(/Waiver System/i)).toBeInTheDocument();
        expect(getByText(/Tie-breaker/i)).toBeInTheDocument();
        expect(getByText(/12/)).toBeInTheDocument(); // roster size always shown
      });
      expect(queryByText(/Edit Waiver Rules/i)).toBeNull();
    });

    test('shows edit button for commissioner', async () => {
      apiClient.get.mockImplementation((url) => {
        if (url === '/auth/me')
          return Promise.resolve({ data: { is_commissioner: true } });
        if (url === '/leagues/1/settings')
          return Promise.resolve({
            data: { waiver_deadline: 'X', roster_size: 14 },
          });
        return Promise.resolve({ data: {} });
      });

      const { getByText } = render(<WaiverRules leagueId={1} />);
      await waitFor(() => {
        expect(getByText(/Edit Waiver Rules/i)).toBeInTheDocument();
        expect(getByText('Waiver Deadline:', { selector: 'strong' })).toBeInTheDocument();
      });
      fireEvent.click(getByText(/Edit Waiver Rules/i));
      expect(mockNavigate).toHaveBeenCalledWith(
        '/commissioner/manage-waiver-rules'
      );
    });
  });

  test('handles API errors gracefully', async () => {
    apiClient.get.mockRejectedValue(new Error('API Error'));

    const { container } = render(
      <WaiverWire
        activeOwnerId={1}
        username="alice"
        leagueName="The Big Show"
      />
    );

    await waitFor(() => {
      expect(container).toBeInTheDocument();
    });
  });
});

describe('ManageWaiverRules (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('fantasyLeagueId', '1');
    vi.resetAllMocks();
  });

  test('renders without crashing and shows existing settings', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({
          data: {
            waiver_deadline: '2026-09-01',
            starting_waiver_budget: 100,
            waiver_system: 'FAAB',
            waiver_tiebreaker: 'standings',
            roster_size: 14,
          },
        });
      }
      if (url === '/leagues/1/waivers/claims') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/leagues/1/waiver-budgets') {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: [] });
    });
    apiClient.put.mockResolvedValue({ data: {} });

    const { container, getByLabelText } = render(<ManageWaiverRules />);
    await waitFor(() => {
      expect(container).toBeInTheDocument();
      expect(getByLabelText(/Roster Size Limit/i)).toBeInTheDocument();
      expect(getByLabelText(/Starting FAAB Budget/i)).toBeInTheDocument();
      // owner budgets may not exist yet
    });
  });

  test('allows updating waiver deadline', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({
          data: {
            waiver_deadline: 'old',
            starting_waiver_budget: 120,
            waiver_system: 'PRIORITY',
            waiver_tiebreaker: 'priority',
            roster_size: 16,
          },
        });
      }
      if (url === '/leagues/1/waivers/claims') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/leagues/1/waiver-budgets') {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: [] });
    });
    apiClient.put.mockResolvedValue({ data: {} });

    const { getByLabelText, getByText } = render(<ManageWaiverRules />);
    await waitFor(() => {
      expect(getByLabelText(/Waiver Deadline/i)).toBeInTheDocument();
      // roster size loads after the settings fetch resolves
      expect(getByLabelText(/Roster Size Limit/i).value).toBe('16');
    });
    fireEvent.change(getByLabelText(/Waiver Deadline/i), {
      target: { value: 'new-deadline' },
    });
    fireEvent.change(getByLabelText(/Starting FAAB Budget/i), {
      target: { value: '150' },
    });
    fireEvent.change(getByLabelText(/Waiver System/i), {
      target: { value: 'BOTH' },
    });
    fireEvent.change(getByLabelText(/Tie-breaker/i), {
      target: { value: 'timestamp' },
    });
    fireEvent.change(getByLabelText(/Roster Size Limit/i), {
      target: { value: '18' },
    });
    fireEvent.click(getByText(/Update Waiver Rules/i));
    await waitFor(() =>
      expect(
        getByText(/Waiver rules updated successfully\./i)
      ).toBeInTheDocument()
    );
    expect(apiClient.put).toHaveBeenCalledWith(
      '/leagues/1/settings',
      expect.objectContaining({
        waiver_deadline: 'new-deadline',
        starting_waiver_budget: 150,
        waiver_system: 'BOTH',
        waiver_tiebreaker: 'timestamp',
        roster_size: 18,
      })
    );
  });

  test('renders claim history rows when data provided', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { waiver_deadline: 'x' } });
      }
      if (url === '/leagues/1/waivers/claims') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              username: 'bob',
              player_name: 'Alice',
              drop_player_name: null,
              bid_amount: 5,
              status: 'PENDING',
            },
          ],
        });
      }
      return Promise.resolve({ data: [] });
    });

    render(<ManageWaiverRules />);
    await waitFor(() => expect(screen.getByText('bob')).toBeInTheDocument());
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('PENDING')).toBeInTheDocument();
  });
});

describe('CommissionerDashboard (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('cards navigate to waiver and trade pages', async () => {
    // ensure any backend requests resolve quickly so the spinner hides
    apiClient.get.mockResolvedValue({ data: {} });
    // dashboard only loads when a leagueId exists
    localStorage.setItem('fantasyLeagueId', '1');

    const { getByText } = render(<CommissionerDashboard />);
    // dashboard shows a splash screen while loading; wait for the real header
    await waitFor(() =>
      expect(getByText(/Commissioner Control Panel/i)).toBeInTheDocument()
    );

    fireEvent.click(getByText(/Edit Waiver Rules/i));
    expect(mockNavigate).toHaveBeenCalledWith(
      '/commissioner/manage-waiver-rules'
    );
    fireEvent.click(getByText(/Edit Trade Rules/i));
    expect(mockNavigate).toHaveBeenCalledWith('/commissioner/manage-trades');
  });
});

// simple smoke for ManageTrades page itself
describe('ManageTrades (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders without crashing (no pending trades)', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/trades/pending') return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });

    const { container } = render(<ManageTrades />);
    await waitFor(() => {
      expect(container).toBeInTheDocument();
    });
  });
});

describe('SiteAdmin (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders without crashing', () => {
    apiClient.get.mockResolvedValue({ data: {} });

    const { container } = render(<SiteAdmin />);

    expect(container).toBeInTheDocument();
  });

  // additional tests may follow...

  test('attempts to fetch admin data if available', async () => {
    apiClient.get.mockResolvedValue({ data: { admins: [] } });

    render(<SiteAdmin />);

    await waitFor(() => {
      expect(screen.getByText(/Site Admin/i)).toBeInTheDocument();
    });
  });

  test('clicking the commissioner button uses router navigation', async () => {
    apiClient.get.mockResolvedValue({ data: {} });

    const { getByRole } = render(<SiteAdmin />);
    // find the action button specifically by role + accessible name
    const button = getByRole('button', { name: /Manage Commissioners/i });

    button.click();
    expect(mockNavigate).toHaveBeenCalledWith('/admin/manage-commissioners');
  });

  test('import schedule button prompts and calls backend', async () => {
    apiClient.post.mockResolvedValue({ data: { detail: 'Import started' } });
    // first prompt returns year, second returns week
    const promptSpy = vi
      .spyOn(window, 'prompt')
      .mockImplementation((msg) =>
        msg.toLowerCase().includes('week') ? '1' : '2025'
      );

    const { getByRole } = render(<SiteAdmin />);
    const button = getByRole('button', { name: /Run Import/i });

    await act(async () => {
      button.click();
    });

    expect(promptSpy).toHaveBeenCalled();
    expect(apiClient.post).toHaveBeenCalledWith(
      '/admin/nfl/schedule/import',
      { year: 2025, week: 1 },
      { timeout: 300000 }
    );
  });
});

// taxi squad UI smoke test (moved to bottom)

describe('MyTeam taxi support', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('displays Taxi Squad heading when a taxi player exists and buttons work', async () => {
    // return user info and the roster; subsequent calls can override
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: {
            user_id: 1,
            username: 'test',
            league_id: 1,
            is_commissioner: false,
          },
        });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({
          data: {
            roster: [
              {
                player_id: 1,
                name: 'TaxiPlayer',
                position: 'RB',
                nfl_team: 'X',
                status: 'BENCH',
                projected_points: 0,
                is_taxi: true,
              },
            ],
          },
        });
      }
      // default stub
      return Promise.resolve({ data: {} });
    });

    apiClient.post.mockResolvedValue({ data: {} });

    render(<MyTeam activeOwnerId={1} />);
    await waitFor(() => {
      const matches = screen.getAllByText(/Taxi Squad/i);
      expect(matches.length).toBeGreaterThan(0);
    });

    const promote = screen.getByText(/Promote/i);
    fireEvent.click(promote);
    expect(apiClient.post).toHaveBeenCalledWith('/team/taxi/promote', {
      player_id: 1,
    });

    // wait for toast to clear (optional) before looking for Taxi button again
    await waitFor(() =>
      expect(
        screen.queryByText(/Player promoted from taxi/i)
      ).toBeInTheDocument()
    );
    // get taxi buttons excluding toast by using getAll and picking the last

    // now simulate a normal bench player and demote
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: {
            user_id: 1,
            username: 'test',
            league_id: 1,
            is_commissioner: false,
          },
        });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({
          data: {
            roster: [
              {
                player_id: 2,
                name: 'BenchPlayer',
                position: 'WR',
                nfl_team: 'Y',
                status: 'BENCH',
                projected_points: 0,
                is_taxi: false,
              },
            ],
          },
        });
      }
      return Promise.resolve({ data: {} });
    });
    render(<MyTeam activeOwnerId={1} />);
    await waitFor(() => {
      expect(screen.getByText('BenchPlayer')).toBeInTheDocument();
    });
    const taxiBtns = screen.getAllByText(/Taxi/i);
    // last one should be the bench button, toast also matches earlier
    const taxiBtn = taxiBtns[taxiBtns.length - 1];
    fireEvent.click(taxiBtn);
    expect(apiClient.post).toHaveBeenCalledWith('/team/taxi/demote', {
      player_id: 2,
    });
  });
});
