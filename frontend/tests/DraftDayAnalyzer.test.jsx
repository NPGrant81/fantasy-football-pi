import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => {
  const client = { get: vi.fn(), post: vi.fn() };
  client.request = vi.fn((config = {}) => {
    const method = String(config.method || 'get').toLowerCase();
    const handler = client[method];
    if (typeof handler !== 'function') {
      return Promise.reject(new Error(`Unsupported method: ${method}`));
    }
    if (method === 'post' || method === 'put' || method === 'patch') {
      return handler(config.url, config.data);
    }
    if (config.params !== undefined) {
      return handler(config.url, { params: config.params });
    }
    return handler(config.url);
  });
  return { default: client };
});

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

const duplicatePlayersPayload = [
  { id: 101, name: 'A.J. Player Jr.', nfl_team: 'BUF', position: 'WR', espn_id: '101' },
  { id: 104, name: 'AJ Player', nfl_team: 'BAL', position: 'WR' },
  { id: 102, name: 'Player B', nfl_team: 'KC', position: 'WR', espn_id: '102' },
  { id: 103, name: 'Player C', nfl_team: 'SF', position: 'RB', espn_id: '103' },
];

const rankingsPayload = [
  { player_id: 101, rank: 1, player_name: 'Player A', position: 'WR', predicted_auction_value: 50, confidence_score: 80, consensus_tier: 'A' },
  { player_id: 102, rank: 2, player_name: 'Player B', position: 'WR', predicted_auction_value: 46, confidence_score: 78, consensus_tier: 'A' },
  { player_id: 103, rank: 3, player_name: 'Player C', position: 'RB', predicted_auction_value: 42, confidence_score: 74, consensus_tier: 'B' },
];

const rankingsPayloadPreviousYear = [
  { player_id: 101, rank: 1, player_name: 'Player A', position: 'WR', predicted_auction_value: 5, confidence_score: 65, consensus_tier: 'C' },
  { player_id: 102, rank: 2, player_name: 'Player B', position: 'WR', predicted_auction_value: 15, confidence_score: 70, consensus_tier: 'B' },
  { player_id: 103, rank: 3, player_name: 'Player C', position: 'RB', predicted_auction_value: 25, confidence_score: 78, consensus_tier: 'B' },
];

const getVisiblePlayerRows = () =>
  screen
    .getAllByRole('button')
    .filter((row) => /Player [A-C]/.test(row.textContent || '') && /BUF|KC|SF/.test(row.textContent || ''));

const buildGetMock = () =>
  vi.fn((url, config = {}) => {
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
      const season = Number(config?.params?.season || 2026);
      return Promise.resolve({
        data: season === 2025 ? rankingsPayloadPreviousYear : rankingsPayload,
      });
    }
    if (url.startsWith('/players/') && url.endsWith('/season-details')) {
      return Promise.resolve({
        data: {
          player_name: 'Player Detail',
          position: 'WR',
          nfl_team: 'BUF',
        },
      });
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

  test('clicking a player row opens Player Info Card modal', async () => {
    render(<DraftDayAnalyzer activeOwnerId={1} activeLeagueId={1} />);

    const playerA = await screen.findByRole('button', { name: /Player A/i });
    fireEvent.click(playerA);

    expect(await screen.findByText('Player Info Card')).toBeInTheDocument();
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        '/players/101/season-details',
        expect.objectContaining({ params: expect.objectContaining({ season: 2026 }) })
      )
    );
  });

  test('sort column persists across position filter changes', async () => {
    render(<DraftDayAnalyzer activeOwnerId={1} activeLeagueId={1} />);

    await screen.findByRole('button', { name: /Player A/i });

    // Click Name twice to sort by name descending (C, B, A)
    fireEvent.click(screen.getByRole('button', { name: 'Name' }));
    fireEvent.click(screen.getByRole('button', { name: 'Name' }));

    // Filter to WR — Player C (RB) is filtered out; remaining WRs sorted name desc: B before A
    fireEvent.click(screen.getByRole('button', { name: 'WR' }));

    await waitFor(() =>
      expect(getVisiblePlayerRows()[0]).toHaveTextContent('Player B')
    );
  });

  test('new search resets sorting to default value desc order', async () => {
    render(<DraftDayAnalyzer activeOwnerId={1} activeLeagueId={1} />);

    await screen.findByRole('button', { name: /Player A/i });

    // Click Name twice to sort by name descending: C, B, A
    fireEvent.click(screen.getByRole('button', { name: 'Name' }));
    fireEvent.click(screen.getByRole('button', { name: 'Name' }));
    await waitFor(() =>
      expect(getVisiblePlayerRows()[0]).toHaveTextContent('Player C')
    );

    // New search should reset sorting to default (value desc) → Player A first
    fireEvent.change(screen.getByPlaceholderText('Search players'), {
      target: { value: 'Player' },
    });

    await waitFor(() =>
      expect(getVisiblePlayerRows()[0]).toHaveTextContent('Player A')
    );
  });

  test('hides duplicate player identities in analyzer list', async () => {
    const baseGet = buildGetMock();
    apiClient.get = vi.fn((url, config = {}) => {
      if (url === '/players/') {
        return Promise.resolve({ data: duplicatePlayersPayload });
      }
      return baseGet(url, config);
    });

    render(<DraftDayAnalyzer activeOwnerId={1} activeLeagueId={1} />);

    await screen.findByRole('button', { name: /Player B/i });

    await waitFor(() => {
      const dedupedRows = screen.getAllByRole('button').filter((row) =>
        /AJ Player|A\.J\. Player/i.test(row.textContent || '')
      );
      expect(dedupedRows).toHaveLength(1);
    });
  });
});
