import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => {
  const client = {
    get: vi.fn(),
  };
  client.request = vi.fn((config = {}) => {
    const method = String(config.method || 'get').toLowerCase();
    const handler = client[method];
    if (typeof handler !== 'function') {
      return Promise.reject(new Error(`Unsupported method: ${method}`));
    }
    return handler(config.url, { params: config.params, data: config.data });
  });
  return { default: client };
});

import PositionalHeatmap from '../src/components/charts/PositionalHeatmap';
import apiClient from '../src/api/client';

describe('PositionalHeatmap', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    localStorage.setItem('fantasyLeagueId', '12');
  });

  test('renders live mode data and suggestions', async () => {
    apiClient.get.mockResolvedValueOnce({
      data: {
        mock_data: false,
        positions: ['QB', 'RB', 'WR', 'TE'],
        rows: [
          { defense_team: 'BUF', weakest_position: 'WR', values: { QB: 20.0, RB: 21.2, WR: 25.4, TE: 13.0 } },
          { defense_team: 'KC', weakest_position: 'QB', values: { QB: 24.8, RB: 18.9, WR: 19.4, TE: 12.5 } },
        ],
        streaming_suggestions: [
          { rank: 1, defense_team: 'BUF', target_position: 'WR', points_allowed: 25.4 },
          { rank: 2, defense_team: 'KC', target_position: 'WR', points_allowed: 19.4 },
        ],
      },
    });

    render(<PositionalHeatmap />);

    expect(await screen.findByText(/Live mode: Aggregated weekly matchup data/i)).toBeInTheDocument();
    expect(screen.getByText('BUF')).toBeInTheDocument();
    expect(screen.getByText(/#1 BUF/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        '/analytics/league/12/positional-heatmap',
        expect.objectContaining({
          params: expect.objectContaining({
            profile: 'standard',
            stream_position: 'WR',
          }),
        })
      );
    });
  });

  test('updates profile and stream focus filters', async () => {
    apiClient.get
      .mockResolvedValueOnce({
        data: {
          mock_data: false,
          positions: ['QB', 'RB', 'WR', 'TE'],
          rows: [{ defense_team: 'DET', weakest_position: 'QB', values: { QB: 22.0, RB: 17.0, WR: 18.0, TE: 10.0 } }],
          streaming_suggestions: [{ rank: 1, defense_team: 'DET', target_position: 'WR', points_allowed: 18.0 }],
        },
      })
      .mockResolvedValueOnce({
        data: {
          mock_data: true,
          fallback_reason: 'missing_opponent_map',
          positions: ['QB', 'RB', 'WR', 'TE'],
          rows: [{ defense_team: 'DET', weakest_position: 'RB', values: { QB: 16.0, RB: 20.5, WR: 17.0, TE: 9.5 } }],
          streaming_suggestions: [{ rank: 1, defense_team: 'DET', target_position: 'WR', points_allowed: 17.0 }],
        },
      })
      .mockResolvedValueOnce({
        data: {
          mock_data: true,
          fallback_reason: 'missing_opponent_map',
          positions: ['QB', 'RB', 'WR', 'TE'],
          rows: [{ defense_team: 'DET', weakest_position: 'RB', values: { QB: 16.0, RB: 20.5, WR: 17.0, TE: 9.5 } }],
          streaming_suggestions: [{ rank: 1, defense_team: 'DET', target_position: 'RB', points_allowed: 20.5 }],
        },
      });

    render(<PositionalHeatmap />);

    const profileSelect = await screen.findByLabelText(/Heatmap profile/i);
    fireEvent.change(profileSelect, { target: { value: 'pass-catching-rbs' } });

    await screen.findByText(/Fallback mode: Mock data/i);

    const refreshedStreamSelect = screen.getByLabelText(/Streaming focus/i);
    fireEvent.change(refreshedStreamSelect, { target: { value: 'RB' } });

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        '/analytics/league/12/positional-heatmap',
        expect.objectContaining({
          params: expect.objectContaining({
            profile: 'pass-catching-rbs',
            stream_position: 'RB',
          }),
        })
      );
    });
  });
});
