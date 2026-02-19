import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { vi } from 'vitest';

vi.mock('axios');

import LeagueSelector from '../src/components/LeagueSelector';

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
    axios.get.mockResolvedValue({ data: leagues });

    const onLeagueSelect = vi.fn();
    render(<LeagueSelector onLeagueSelect={onLeagueSelect} />);

    expect(screen.getByText(/Loading Leagues/i)).toBeInTheDocument();

    await waitFor(() => expect(axios.get).toHaveBeenCalled());
    expect(screen.getByText('L1')).toBeInTheDocument();
    expect(screen.getByText('L2')).toBeInTheDocument();
  });

  test('create league flow calls post and updates list', async () => {
    axios.get.mockResolvedValue({ data: [] });
    axios.post.mockResolvedValue({ data: { id: 3, name: 'NewLeague' } });

    render(<LeagueSelector onLeagueSelect={() => {}} />);

    await waitFor(() => expect(axios.get).toHaveBeenCalled());

    // Click create toggle
    const user = userEvent.setup();
    await user.click(screen.getByText('+ Create New League'));
    const input = screen.getByPlaceholderText(/e.g. Dynasty 2026/i);
    await user.type(input, 'NewLeague');
    await user.click(screen.getByText('SAVE'));

    await waitFor(() => expect(axios.post).toHaveBeenCalled());
    expect(screen.getByText('NewLeague')).toBeInTheDocument();
  });
});
