import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

vi.mock('../src/hooks/useDraftTimer', () => ({
  useDraftTimer: () => ({
    timeLeft: 5,
    start: vi.fn(),
    reset: vi.fn(),
    isActive: false,
  }),
}));

vi.mock('../src/components/draft', () => ({
  AuctionBlock: () => <div data-testid="auction-block">Auction Block</div>,
  SessionHeader: () => <div data-testid="session-header">Session Header</div>,
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

describe('DraftBoard analyzer isolation', () => {
  beforeEach(() => {
    vi.restoreAllMocks();

    apiClient.get = vi.fn((url) => {
      if (url.startsWith('/leagues/owners')) {
        return Promise.resolve({ data: league1OwnersFixture });
      }

      if (url.startsWith('/players/')) {
        return Promise.resolve({ data: league1PlayersFixture });
      }

      if (url.startsWith('/draft/history')) {
        return Promise.resolve({ data: [] });
      }

      if (url.startsWith('/leagues/1/budgets')) {
        return Promise.resolve({ data: league1BudgetsFixture });
      }

      if (url.startsWith('/draft/rankings')) {
        return Promise.resolve({ data: [] });
      }

      if (url === '/leagues/1') {
        return Promise.resolve({ data: league1MetaFixture });
      }

      if (url === '/auth/me') {
        return Promise.resolve({
          data: { username: 'nickgrant', is_commissioner: true },
        });
      }

      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: league1SettingsFixture });
      }

      return Promise.resolve({ data: {} });
    });

    apiClient.post = vi.fn().mockResolvedValue({ data: {} });
  });

  test('does not render analyzer modules or call analyzer endpoints on mount', async () => {
    render(<DraftBoard token="token" activeOwnerId={1} activeLeagueId={1} />);

    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('/players/')
      )
    );

    expect(screen.getByText('Draft Board')).toBeInTheDocument();
    expect(screen.queryByText('Analyzer Insights')).not.toBeInTheDocument();
    expect(screen.queryByText('Draft Day Advisor')).not.toBeInTheDocument();
    expect(screen.queryByText('Perspective Simulation')).not.toBeInTheDocument();

    expect(apiClient.post).not.toHaveBeenCalledWith(
      '/draft/model/predict',
      expect.anything()
    );
    expect(apiClient.post).not.toHaveBeenCalledWith(
      '/advisor/draft-day/event',
      expect.anything()
    );
    expect(apiClient.post).not.toHaveBeenCalledWith(
      '/advisor/draft-day/query',
      expect.anything()
    );
    expect(apiClient.post).not.toHaveBeenCalledWith(
      '/draft/simulation',
      expect.anything()
    );
  });
});
