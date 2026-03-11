import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}));

import ScoringRulesModal from '../src/pages/commissioner/components/ScoringRulesModal';
import apiClient from '../src/api/client';

describe('ScoringRulesModal', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('renders nothing when closed', () => {
    const { container } = render(<ScoringRulesModal open={false} onClose={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  test('fetches and displays scoring rules when opened', async () => {
    apiClient.get.mockResolvedValueOnce({
      data: [
        {
          id: 1,
          category: 'passing',
          event_name: 'passing_tds',
          calculation_type: 'flat_bonus',
          point_value: 4,
          applicable_positions: ['QB'],
          season_year: 2026,
        },
      ],
    });

    render(<ScoringRulesModal open={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('/scoring/rules')
      );
      expect(screen.getByText('passing_tds')).toBeInTheDocument();
    });
  });

  test('shows human-readable calculation type label', async () => {
    apiClient.get.mockResolvedValueOnce({
      data: [
        {
          id: 2,
          category: 'receiving',
          event_name: 'receptions',
          calculation_type: 'ppr',
          point_value: 1,
          applicable_positions: [],
          season_year: null,
        },
      ],
    });

    render(<ScoringRulesModal open={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('PPR')).toBeInTheDocument();
      expect(screen.queryByText('ppr')).not.toBeInTheDocument();
    });
  });

  test('shows no-rules message when list is empty', async () => {
    apiClient.get.mockResolvedValueOnce({ data: [] });

    render(<ScoringRulesModal open={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/No scoring rules have been configured/i)).toBeInTheDocument();
    });
  });

  test('shows error when fetch fails', async () => {
    apiClient.get.mockRejectedValueOnce({ message: 'Failed to load scoring rules.' });

    render(<ScoringRulesModal open={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load scoring rules/i)).toBeInTheDocument();
    });
  });

  test('shows All seasons when season_year is null', async () => {
    apiClient.get.mockResolvedValueOnce({
      data: [
        {
          id: 3,
          category: 'rushing',
          event_name: 'rushing_yards',
          calculation_type: 'per_unit',
          point_value: 0.1,
          applicable_positions: ['RB'],
          season_year: null,
        },
      ],
    });

    render(<ScoringRulesModal open={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('All seasons')).toBeInTheDocument();
    });
  });
});
