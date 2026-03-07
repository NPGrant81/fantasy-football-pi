import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import ManageScoringRules from '../src/pages/commissioner/ManageScoringRules';
import apiClient from '../src/api/client';

describe('ManageScoringRules page', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    apiClient.get.mockResolvedValue({ data: [] });
  });

  test('loads rules from backend on mount', async () => {
    apiClient.get.mockResolvedValueOnce({
      data: [
        {
          id: 7,
          category: 'passing',
          event_name: 'passing_yards',
          range_min: 0,
          range_max: 999,
          point_value: 0.04,
          calculation_type: 'per_unit',
          applicable_positions: ['QB'],
          season_year: 2026,
        },
      ],
    });

    render(<ManageScoringRules />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalled();
      expect(screen.getByText('passing_yards')).toBeInTheDocument();
    });
  });

  test('submits create rule payload', async () => {
    apiClient.post.mockResolvedValue({ data: { id: 8 } });
    render(<ManageScoringRules />);

    fireEvent.change(screen.getByPlaceholderText(/Category/i), {
      target: { value: 'passing' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Event Name/i), {
      target: { value: 'passing_tds' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Point Value/i), {
      target: { value: '4' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Positions/i), {
      target: { value: 'QB' },
    });

    fireEvent.click(screen.getByRole('button', { name: /Add Rule/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/scoring/rules',
        expect.objectContaining({
          category: 'passing',
          event_name: 'passing_tds',
          point_value: 4,
          applicable_positions: ['QB'],
        })
      );
    });
  });

  test('runs scoring simulator preview', async () => {
    apiClient.post.mockResolvedValueOnce({
      data: {
        points: 18,
        rules_evaluated: 4,
      },
    });

    render(<ManageScoringRules />);

    fireEvent.click(screen.getByRole('button', { name: /Run Preview/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/scoring/calculate/player-preview',
        expect.objectContaining({ position: 'QB' })
      );
      expect(screen.getByText(/Total Preview Points: 18/i)).toBeInTheDocument();
    });
  });
});
