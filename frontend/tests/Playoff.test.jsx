import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}));

import PlayoffBracket from '../src/pages/playoffs/PlayoffBracket';
import apiClient from '../src/api/client';

describe('PlayoffBracket page', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
    localStorage.setItem('fantasyLeagueId', '1');
  });

  test('shows heading and fetches bracket when expanded', async () => {
    const bracketData = {
      championship: [
        {
          match_id: 'm1',
          round: 1,
          is_bye: true,
          team_1_id: 1,
          team_2_id: null,
          winner_to: 'r2_m1',
        },
      ],
      consolation: [],
    };

    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url.startsWith('/playoffs/bracket')) {
        return Promise.resolve({ data: bracketData });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<PlayoffBracket />);
    expect(
      screen.getByRole('heading', { level: 1, name: /Playoff Bracket/i })
    ).toBeInTheDocument();

    // expand accordion by clicking the second element that matches the
    // text (the first is the page heading, the second is the summary)
    const matches = screen.getAllByText(/Playoff Bracket/i);
    expect(matches.length).toBeGreaterThan(1);
    matches[1].click();

    await waitFor(() => {
      expect(screen.getByText(/m1/)).toBeInTheDocument();
    });
  });
});
