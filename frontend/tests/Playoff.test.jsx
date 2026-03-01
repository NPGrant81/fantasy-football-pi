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
      if (url.startsWith('/playoffs/seasons')) {
        // simulate normal array response
        return Promise.resolve({ data: [2026, 2025] });
      }
      if (url.startsWith('/playoffs/seasons-object')) {
        // some buggy API shapes may wrap the list inside `seasons` key
        return Promise.resolve({ data: { seasons: [2026, 2025] } });
      }
      if (url.startsWith('/playoffs/bracket')) {
        return Promise.resolve({ data: bracketData });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    const setSubHeader = vi.fn();
    render(
      <PlayoffBracket username="alice" leagueId={1} setSubHeader={setSubHeader} />
    );
    expect(
      screen.getByRole('heading', { level: 1, name: /Playoff Bracket/i })
    ).toBeInTheDocument();
    // subHeader prop should be invoked with user/league title (first call)
    expect(setSubHeader).toHaveBeenCalledWith(expect.stringContaining('alice'));
    // league name is already part of the heading so we don't insist on it here

    // season selector should be rendered (wait for fetch effect)
    expect(await screen.findByText(/Season:/i)).toBeInTheDocument();
    // there should be at least one option inside the dropdown
    expect(screen.getByRole('combobox')).toHaveTextContent('2026');

    // expand accordion by clicking the second element that matches the
    // text (the first is the page heading, the second is the summary)
    const matches = screen.getAllByText(/Playoff Bracket/i);
    expect(matches.length).toBeGreaterThan(1);
    matches[1].click();

    await waitFor(() => {
      expect(screen.getByText(/m1/)).toBeInTheDocument();
    });
  });

  test('handles seasons endpoint wrapped in object', async () => {
    // bracket same as before
    const bracketData2 = { championship: [], consolation: [] };
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url.startsWith('/playoffs/seasons')) {
        // respond with wrapped object instead of plain array
        return Promise.resolve({ data: { seasons: [2024] } });
      }
      if (url.startsWith('/playoffs/bracket')) {
        return Promise.resolve({ data: bracketData2 });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(
      <PlayoffBracket username="alice" leagueId={1} setSubHeader={() => {}} />
    );
    // make sure selector shows the one season
    expect(await screen.findByDisplayValue('2024')).toBeInTheDocument();
  });
});
