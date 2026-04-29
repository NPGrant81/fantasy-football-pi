import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

// Use stable mocks so that reset's identity doesn't change on every render
// (which would cause handlePause to be recreated every render via useCallback).
const timerMocks = {
  onTimeUp: null,
  reset: vi.fn(),
  start: vi.fn(),
};

vi.mock('../src/hooks/useDraftTimer', () => ({
  useDraftTimer: (initial, onTimeUp) => {
    timerMocks.onTimeUp = onTimeUp;
    return {
      timeLeft: 5,
      start: timerMocks.start,
      reset: timerMocks.reset,
      isActive: false,
    };
  },
}));

vi.mock('../src/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

// SessionHeader mock that wires up the onPause button so tests can click it
vi.mock('../src/components/draft', () => ({
  AuctionBlock: ({ canDraft, isPaused }) => (
    <div data-testid="auction-block">
      <span data-testid="can-draft">{canDraft ? 'can-draft' : 'no-draft'}</span>
      <span data-testid="is-paused-prop">{isPaused ? 'paused' : 'active'}</span>
    </div>
  ),
  SessionHeader: ({ onPause, isPaused }) => (
    <div data-testid="session-header">
      <button data-testid="pause-btn" onClick={onPause}>
        {isPaused ? 'Resume' : 'Pause'}
      </button>
    </div>
  ),
  DraftHistoryFeed: () => <div data-testid="history-feed">History Feed</div>,
}));

vi.mock('../src/components/draft/DraftBoardGrid', () => ({
  default: () => <div data-testid="draft-board-grid">Draft Board Grid</div>,
}));

vi.mock('../src/components/draft/BestAvailableList', () => ({
  default: () => <div data-testid="best-available-list">Best Available</div>,
}));

vi.mock('../src/components/player/PlayerIdentityCard', () => ({
  default: () => <div data-testid="player-identity-card">Player Identity</div>,
}));

import apiClient from '../src/api/client';
import DraftBoard from '../src/pages/DraftBoard';
import {
  league1BudgetsFixture,
  league1MetaFixture,
  league1OwnersFixture,
  league1PlayersFixture,
  league1SettingsFixture,
} from './fixtures/draftboardLeague1Fixture';

function setupApiMocks() {
  apiClient.get = vi.fn((url) => {
    if (url.startsWith('/leagues/owners')) {
      return Promise.resolve({ data: league1OwnersFixture });
    }
    if (url.startsWith('/players/')) return Promise.resolve({ data: league1PlayersFixture });
    if (url.startsWith('/draft/history')) return Promise.resolve({ data: [] });
    if (url.startsWith('/leagues/1/budgets')) {
      return Promise.resolve({ data: league1BudgetsFixture });
    }
    if (url.startsWith('/draft/rankings')) return Promise.resolve({ data: [] });
    if (url === '/leagues/1') return Promise.resolve({ data: league1MetaFixture });
    if (url === '/auth/me') {
      return Promise.resolve({ data: { username: 'nickgrant', is_commissioner: true } });
    }
    if (url.startsWith('/leagues/1/settings')) {
      return Promise.resolve({ data: league1SettingsFixture });
    }
    return Promise.resolve({ data: {} });
  });
  apiClient.post = vi.fn().mockResolvedValue({ data: {} });
}

describe('DraftBoard pause interactions', () => {
  beforeEach(() => {
    timerMocks.onTimeUp = null;
    timerMocks.reset.mockClear();
    timerMocks.start.mockClear();
    setupApiMocks();
  });

  test('isPaused prop is passed as false initially, true after clicking Pause', async () => {
    const user = userEvent.setup();
    render(<DraftBoard token="tok" activeOwnerId={1} activeLeagueId={1} />);

    await waitFor(() =>
      expect(screen.getByTestId('pause-btn')).toBeInTheDocument()
    );

    expect(screen.getByTestId('is-paused-prop').textContent).toBe('active');
    expect(screen.getByTestId('pause-btn').textContent).toBe('Pause');

    await user.click(screen.getByTestId('pause-btn'));

    await waitFor(() =>
      expect(screen.getByTestId('is-paused-prop').textContent).toBe('paused')
    );
    expect(screen.getByTestId('pause-btn').textContent).toBe('Resume');
  });

  test('canDraft is false while paused (submit action disabled)', async () => {
    const user = userEvent.setup();
    render(<DraftBoard token="tok" activeOwnerId={1} activeLeagueId={1} />);

    await waitFor(() =>
      expect(screen.getByTestId('pause-btn')).toBeInTheDocument()
    );

    // canDraft is already false (no playerName), but isPaused also contributes
    await user.click(screen.getByTestId('pause-btn'));

    await waitFor(() =>
      expect(screen.getByTestId('is-paused-prop').textContent).toBe('paused')
    );
    expect(screen.getByTestId('can-draft').textContent).toBe('no-draft');
  });

  test('timer expiry does not POST /draft/pick when paused', async () => {
    const user = userEvent.setup();
    render(<DraftBoard token="tok" activeOwnerId={1} activeLeagueId={1} />);

    await waitFor(() =>
      expect(screen.getByTestId('pause-btn')).toBeInTheDocument()
    );

    // Pause the draft — re-render updates onTimeUp closure to have isPaused=true
    await user.click(screen.getByTestId('pause-btn'));

    await waitFor(() =>
      expect(screen.getByTestId('is-paused-prop').textContent).toBe('paused')
    );

    // Simulate timer expiry with the captured onTimeUp callback
    expect(timerMocks.onTimeUp).not.toBeNull();
    act(() => {
      timerMocks.onTimeUp(true);
    });

    expect(apiClient.post).not.toHaveBeenCalledWith(
      '/draft/pick',
      expect.anything()
    );
  });

  test('timer reset is called when pausing to prevent immediate re-expiry on resume', async () => {
    const user = userEvent.setup();
    render(<DraftBoard token="tok" activeOwnerId={1} activeLeagueId={1} />);

    await waitFor(() =>
      expect(screen.getByTestId('pause-btn')).toBeInTheDocument()
    );

    await user.click(screen.getByTestId('pause-btn'));

    await waitFor(() =>
      expect(screen.getByTestId('is-paused-prop').textContent).toBe('paused')
    );
    expect(timerMocks.reset).toHaveBeenCalled();
  });

  test('resuming re-enables interactions (isPaused returns to false)', async () => {
    const user = userEvent.setup();
    render(<DraftBoard token="tok" activeOwnerId={1} activeLeagueId={1} />);

    await waitFor(() =>
      expect(screen.getByTestId('pause-btn')).toBeInTheDocument()
    );

    // Pause
    await user.click(screen.getByTestId('pause-btn'));
    await waitFor(() =>
      expect(screen.getByTestId('is-paused-prop').textContent).toBe('paused')
    );

    // Resume
    await user.click(screen.getByTestId('pause-btn'));
    await waitFor(() =>
      expect(screen.getByTestId('is-paused-prop').textContent).toBe('active')
    );
    expect(screen.getByTestId('pause-btn').textContent).toBe('Pause');
  });
});
