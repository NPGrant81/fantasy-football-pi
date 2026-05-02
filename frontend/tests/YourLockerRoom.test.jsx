/**
 * Tests for issue #173 — Start/Sit Sorter fixes:
 *   1. Recommended Sits section was always empty (recState used 'BENCH' but filter used 'SIT')
 *   2. "Apply to My Lineup" button was missing
 */
import { render, screen, waitFor, fireEvent, act } from '../src/setupTests';
import { vi } from 'vitest';
import YourLockerRoom from '@/pages/team-owner/YourLockerRoom';
import apiClient from '@/api/client';

// Roster designed so buildWeeklyStartSitPlan produces at least one sit:
//   QB:1, RB:2+FLEX(RB Three), WR:2 → WR Three has no slot → SIT
const testRoster = [
  { id: 1,  player_id: 1,  name: 'QB One',   position: 'QB',  nfl_team: 'DAL', status: 'STARTER', projected_points: 25 },
  { id: 2,  player_id: 2,  name: 'RB One',   position: 'RB',  nfl_team: 'DAL', status: 'STARTER', projected_points: 20 },
  { id: 3,  player_id: 3,  name: 'RB Two',   position: 'RB',  nfl_team: 'CHI', status: 'STARTER', projected_points: 8  },
  { id: 4,  player_id: 4,  name: 'RB Three', position: 'RB',  nfl_team: 'LAR', status: 'BENCH',   projected_points: 5.5 },
  { id: 5,  player_id: 5,  name: 'WR One',   position: 'WR',  nfl_team: 'DAL', status: 'STARTER', projected_points: 18 },
  { id: 6,  player_id: 6,  name: 'WR Two',   position: 'WR',  nfl_team: 'CHI', status: 'STARTER', projected_points: 6  },
  { id: 7,  player_id: 7,  name: 'WR Three', position: 'WR',  nfl_team: 'LAR', status: 'BENCH',   projected_points: 5  },
  { id: 8,  player_id: 8,  name: 'TE One',   position: 'TE',  nfl_team: 'DAL', status: 'STARTER', projected_points: 12 },
  { id: 9,  player_id: 9,  name: 'DEF One',  position: 'DEF', nfl_team: 'DAL', status: 'STARTER', projected_points: 9  },
  { id: 10, player_id: 10, name: 'K One',    position: 'K',   nfl_team: 'DAL', status: 'STARTER', projected_points: 7  },
];

function setupMocks() {
  apiClient.get.mockImplementation((url) => {
    if (url === '/auth/me') {
      return Promise.resolve({
        data: { user_id: 1, username: 'alice', league_id: 1, is_commissioner: false },
      });
    }
    if (url === '/leagues/1') {
      return Promise.resolve({ data: { name: 'Test League', draft_status: 'COMPLETED' } });
    }
    if (url.startsWith('/leagues/owners')) {
      return Promise.resolve({ data: [] });
    }
    if (url.startsWith('/leagues/1/settings')) {
      return Promise.resolve({ data: { starting_slots: {}, scoring_rules: [] } });
    }
    if (url.startsWith('/dashboard/')) {
      return Promise.resolve({ data: { roster: testRoster } });
    }
    if (url.startsWith('/team/1?week=')) {
      return Promise.resolve({ data: { roster: testRoster } });
    }
    return Promise.resolve({ data: {} });
  });
  apiClient.post.mockResolvedValue({ data: {} });
}

describe('YourLockerRoom — Start/Sit Sorter (issue #173)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('Recommended Sits section shows bench players (not empty)', async () => {
    setupMocks();
    render(<YourLockerRoom activeOwnerId={1} />);

    // Wait for roster load
    await waitFor(() => {
      expect(screen.queryByText(/QB One/i)).toBeInTheDocument();
    });

    // Switch to Recommended mode
    const recommendedBtn = screen.getByRole('button', { name: /^Recommended$/i });
    await act(async () => {
      fireEvent.click(recommendedBtn);
    });

    // Heading should change to Start/Sit Sorter
    await waitFor(() => {
      expect(screen.getByText(/Start\/Sit Sorter/i)).toBeInTheDocument();
    });

    // WR Three has the lowest projected among WRs and gets no slot → should be a SIT
    await waitFor(() => {
      const sitsSection = screen.getByText(/Recommended Sits/i).closest('div');
      expect(sitsSection).toBeInTheDocument();
      expect(screen.getByText('WR Three')).toBeInTheDocument();
    });

    // The count badge on Recommended Sits should be > 0
    const sitsHeading = screen.getByText(/Recommended Sits/i);
    const badge = sitsHeading.parentElement.querySelector('span');
    expect(Number(badge.textContent)).toBeGreaterThan(0);
  });

  test('Apply to My Lineup button appears in Recommended mode', async () => {
    setupMocks();
    render(<YourLockerRoom activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.queryByText(/QB One/i)).toBeInTheDocument();
    });

    // Button should NOT be present in actual mode
    expect(screen.queryByRole('button', { name: /Apply to My Lineup/i })).toBeNull();

    // Switch to Recommended mode
    const recommendedBtn = screen.getByRole('button', { name: /^Recommended$/i });
    await act(async () => {
      fireEvent.click(recommendedBtn);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Apply to My Lineup/i })).toBeInTheDocument();
    });
  });

  test('Apply to My Lineup switches back to Actual view and shows toast', async () => {
    setupMocks();
    render(<YourLockerRoom activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.queryByText(/QB One/i)).toBeInTheDocument();
    });

    // Enter Recommended mode
    const recommendedBtn = screen.getByRole('button', { name: /^Recommended$/i });
    await act(async () => {
      fireEvent.click(recommendedBtn);
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Apply to My Lineup/i })).toBeInTheDocument();
    });

    // Click Apply
    const applyBtn = screen.getByRole('button', { name: /Apply to My Lineup/i });
    await act(async () => {
      fireEvent.click(applyBtn);
    });

    // Should switch back to actual mode (Lineup Builder title)
    await waitFor(() => {
      expect(screen.getByText(/Lineup Builder/i)).toBeInTheDocument();
    });

    // Toast message should appear
    await waitFor(() => {
      expect(
        screen.getByText(/Recommended lineup applied/i)
      ).toBeInTheDocument();
    });
  });

  test('Owner Management button is hidden for non-commissioners', async () => {
    setupMocks();
    render(<YourLockerRoom activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.queryByText(/QB One/i)).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /Owner Management/i })).toBeNull();
  });

  test('lineup view omits unrelated trade controls in top actions', async () => {
    setupMocks();
    render(<YourLockerRoom activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.queryByText(/QB One/i)).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /Propose Trade/i })).toBeNull();
    expect(screen.queryByText(/Pending Trades/i)).toBeNull();
  });

  test('disables QB starter slot when league config turns QB off', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { user_id: 1, username: 'alice', league_id: 1, is_commissioner: false },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'Portable League', draft_status: 'COMPLETED' } });
      }
      if (url.startsWith('/leagues/owners')) {
        return Promise.resolve({ data: [] });
      }
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({
          data: {
            starting_slots: {
              ACTIVE_ROSTER_SIZE: 1,
              ALLOW_PARTIAL_LINEUP: 1,
              QB: 0,
              MAX_QB: 0,
              RB: 1,
              MAX_RB: 1,
              WR: 0,
              MAX_WR: 0,
              TE: 0,
              MAX_TE: 0,
              K: 0,
              MAX_K: 0,
              DEF: 0,
              MAX_DEF: 0,
              FLEX: 0,
              MAX_FLEX: 0,
            },
            scoring_rules: [],
          },
        });
      }
      if (url.startsWith('/dashboard/')) {
        return Promise.resolve({
          data: {
            roster: [
              { id: 1, player_id: 1, name: 'QB One', position: 'QB', nfl_team: 'DAL', status: 'STARTER' },
              { id: 2, player_id: 2, name: 'RB One', position: 'RB', nfl_team: 'DAL', status: 'STARTER' },
            ],
          },
        });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({
          data: {
            roster: [
              { id: 1, player_id: 1, name: 'QB One', position: 'QB', nfl_team: 'DAL', status: 'STARTER' },
              { id: 2, player_id: 2, name: 'RB One', position: 'RB', nfl_team: 'DAL', status: 'STARTER' },
            ],
          },
        });
      }
      return Promise.resolve({ data: {} });
    });

    apiClient.post.mockResolvedValue({ data: {} });

    render(<YourLockerRoom activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.getByText(/RB One/i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.queryByText(/QB 0/)).toBeNull();
      expect(screen.getByText(/RB 1/)).toBeInTheDocument();
    });
  });

  test('Owner Management button is removed for commissioners too', async () => {
    setupMocks();
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { user_id: 1, username: 'alice', league_id: 1, is_commissioner: true },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'Test League', draft_status: 'COMPLETED' } });
      }
      if (url.startsWith('/leagues/owners')) {
        return Promise.resolve({ data: [] });
      }
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { starting_slots: {}, scoring_rules: [] } });
      }
      if (url.startsWith('/dashboard/')) {
        return Promise.resolve({ data: { roster: testRoster } });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({ data: { roster: testRoster } });
      }
      return Promise.resolve({ data: {} });
    });

    apiClient.post.mockResolvedValue({ data: {} });

    render(<YourLockerRoom activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.queryByText(/QB One/i)).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /Owner Management/i })).toBeNull();
  });

  test('loads selected future week roster context', async () => {
    const week3Roster = [
      { id: 20, player_id: 20, name: 'RB Week Three', position: 'RB', nfl_team: 'NYG', status: 'STARTER' },
    ];
    setupMocks();
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { user_id: 1, username: 'alice', league_id: 1, is_commissioner: false },
        });
      }
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'Test League', draft_status: 'COMPLETED' } });
      }
      if (url.startsWith('/leagues/owners')) {
        return Promise.resolve({ data: [] });
      }
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { starting_slots: {}, scoring_rules: [] } });
      }
      if (url.startsWith('/dashboard/')) {
        return Promise.resolve({ data: { roster: testRoster } });
      }
      if (url === '/team/1?week=3') {
        return Promise.resolve({ data: { roster: week3Roster, lineup_submitted: false } });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({ data: { roster: testRoster } });
      }
      return Promise.resolve({ data: {} });
    });
    apiClient.post.mockResolvedValue({ data: {} });

    render(<YourLockerRoom activeOwnerId={1} />);

    await waitFor(() => {
      expect(screen.getByText(/QB One/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Week/i), { target: { value: '3' } });

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/team/1?week=3');
    });

    await waitFor(() => {
      expect(screen.getByText(/RB Week Three/i)).toBeInTheDocument();
    });
  });
});
