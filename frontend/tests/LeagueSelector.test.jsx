import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import LeagueSelector from '../src/components/LeagueSelector';
import apiClient from '../src/api/client';

describe('LeagueSelector', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
  });

  test('shows loading then leagues from API', async () => {
    const leagues = [
      { id: 1, name: 'L1' },
      { id: 2, name: 'L2' },
    ];
    apiClient.get.mockResolvedValue({ data: leagues });
    apiClient.post.mockResolvedValue({ data: { message: 'ok' } });

    const onLeagueSelect = vi.fn();
    render(<LeagueSelector onLeagueSelect={onLeagueSelect} />);

    expect(screen.getByText(/Loading Leagues/i)).toBeInTheDocument();

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/leagues/'));
    expect(screen.getByText('L1')).toBeInTheDocument();
    expect(screen.getByText('L2')).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByText('L1'));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith('/leagues/join', null, {
        params: { league_id: 1 },
      })
    );
    expect(onLeagueSelect).toHaveBeenCalledWith('1');
  });

  test('create league flow calls post and updates list', async () => {
    apiClient.get.mockResolvedValue({ data: [] });
    apiClient.post.mockResolvedValue({ data: { id: 3, name: 'NewLeague' } });

    render(<LeagueSelector onLeagueSelect={() => {}} />);

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/leagues/'));

    // Click create toggle
    const user = userEvent.setup();
    await user.click(screen.getByText('+ Create New League'));
    const input = screen.getByPlaceholderText(/e.g. Dynasty 2026/i);
    await user.type(input, 'NewLeague');
    await user.click(screen.getByText('SAVE'));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalled());
    expect(screen.getByText('NewLeague')).toBeInTheDocument();
  });
});
