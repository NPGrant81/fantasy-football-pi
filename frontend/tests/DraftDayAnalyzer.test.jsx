import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

vi.mock('../src/components/draft/insights/PlayerInsightCard', () => ({
  default: () => <div data-testid="player-insight-card">Player Insight</div>,
}));

vi.mock('../src/components/draft/insights/OwnerStrategyPanel', () => ({
  default: () => <div data-testid="owner-strategy-panel">Owner Strategy</div>,
}));

vi.mock('../src/components/draft/insights/DraftDynamicsPanel', () => ({
  default: () => <div data-testid="draft-dynamics-panel">Draft Dynamics</div>,
}));

import apiClient from '../src/api/client';
import DraftDayAnalyzer from '../src/pages/DraftDayAnalyzer';

const ownersPayload = [
  { id: 1, username: 'alice', team_name: 'Alpha' },
  { id: 2, username: 'bob', team_name: 'Beta' },
];

const playersPayload = [
  { id: 101, name: 'Player A', nfl_team: 'BUF', position: 'WR' },
  { id: 102, name: 'Player B', nfl_team: 'KC', position: 'WR' },
  { id: 103, name: 'Player C', nfl_team: 'SF', position: 'RB' },
];

const rankingsPayload = [
  { player_id: 101, rank: 1, player_name: 'Player A', position: 'WR', predicted_auction_value: 50, confidence_score: 80, consensus_tier: 'A' },
  { player_id: 102, rank: 2, player_name: 'Player B', position: 'WR', predicted_auction_value: 46, confidence_score: 78, consensus_tier: 'A' },
  { player_id: 103, rank: 3, player_name: 'Player C', position: 'RB', predicted_auction_value: 42, confidence_score: 74, consensus_tier: 'B' },
];

const buildGetMock = () =>
  vi.fn((url) => {
    if (url.startsWith('/leagues/owners')) {
      return Promise.resolve({ data: ownersPayload });
    }
    if (url === '/players/') {
      return Promise.resolve({ data: playersPayload });
    }
    if (url.startsWith('/leagues/1/settings')) {
      return Promise.resolve({ data: { draft_year: 2026 } });
    }
    if (url.startsWith('/draft/history')) {
      return Promise.resolve({ data: [] });
    }
    if (url.startsWith('/draft/rankings')) {
      return Promise.resolve({ data: rankingsPayload });
    }
    return Promise.resolve({ data: [] });
  });

describe('DraftDayAnalyzer advisor actions', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    apiClient.get = buildGetMock();
    apiClient.post = vi.fn((url) => {
      if (url === '/draft/model/predict') {
        return Promise.resolve({
          data: {
            recommendations: [
              {
                player_name: 'Player A',
                position: 'WR',
                recommended_bid: 50,
                predicted_value: 50,
                risk_score: 22,
                value_score: 50,
                tier: 'A',
                flags: [],
              },
            ],
          },
        });
      }

      if (url === '/advisor/draft-day/query') {
        return Promise.resolve({
          data: {
            event_type: 'user_query',
            message_type: 'comparison',
            headline: 'Advisor result',
            body: 'Action handled.',
            alerts: [],
            quick_actions: ['Compare', 'Simulate', 'Explain'],
          },
        });
      }

      return Promise.resolve({ data: {} });
    });
  });

  test('Compare sends compared_player_id and opens drawer details', async () => {
    render(<DraftDayAnalyzer activeOwnerId={1} activeLeagueId={1} />);

    const playerA = await screen.findByRole('button', { name: /Player A/i });
    fireEvent.click(playerA);

    const compareButton = await screen.findByRole('button', { name: 'Compare' });
    await waitFor(() => expect(compareButton).toBeEnabled());

    fireEvent.click(compareButton);

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        '/advisor/draft-day/query',
        expect.objectContaining({
          owner_id: 1,
          league_id: 1,
          player_id: 101,
          compared_player_id: 102,
        })
      )
    );

    expect(await screen.findByText('Compare Details')).toBeInTheDocument();
    expect(await screen.findByText(/Advisor result/i)).toBeInTheDocument();
  });

  test('Explain sends query without compared player and opens drawer details', async () => {
    render(<DraftDayAnalyzer activeOwnerId={1} activeLeagueId={1} />);

    const playerA = await screen.findByRole('button', { name: /Player A/i });
    fireEvent.click(playerA);

    const explainButton = await screen.findByRole('button', { name: 'Explain' });
    await waitFor(() => expect(explainButton).toBeEnabled());

    fireEvent.click(explainButton);

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        '/advisor/draft-day/query',
        expect.objectContaining({
          owner_id: 1,
          league_id: 1,
          player_id: 101,
          compared_player_id: null,
        })
      )
    );

    expect(await screen.findByText('Explain Details')).toBeInTheDocument();
    expect(await screen.findByText(/Action handled/i)).toBeInTheDocument();
  });
});
