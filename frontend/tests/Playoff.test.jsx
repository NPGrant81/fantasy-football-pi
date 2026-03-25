import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => {
  const client = {
    get: vi.fn(),
    post: vi.fn(),
  };
  client.request = vi.fn((config = {}) => {
    const method = String(config.method || 'get').toLowerCase();
    const handler = client[method];
    if (typeof handler !== 'function') {
      return Promise.reject(new Error(`Unsupported method: ${method}`));
    }
    if (config.params !== undefined || config.data !== undefined) {
      return handler(config.url, { params: config.params, data: config.data });
    }
    return handler(config.url);
  });
  return { default: client };
});

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
      seeding_policy: {
        playoff_consolation: true,
        round_labels: {
          championship: { '1': 'Wildcard Round' },
          consolation: {},
        },
      },
    };

    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url.startsWith('/playoffs/seasons')) {
        return Promise.resolve({ data: [2026, 2025] });
      }
      if (url.startsWith('/playoffs/bracket')) {
        return Promise.resolve({ data: bracketData });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
    apiClient.post.mockResolvedValue({ data: { ok: true } });

    const setSubHeader = vi.fn();
    render(
      <MemoryRouter>
        <PlayoffBracket username="alice" leagueId={1} setSubHeader={setSubHeader} />
      </MemoryRouter>
    );
    expect(
      screen.getByRole('heading', { level: 1, name: /Playoff Bracket/i })
    ).toBeInTheDocument();
    // subHeader prop should be invoked with user/league title
    expect(setSubHeader).toHaveBeenCalledWith(expect.stringContaining('alice'));

    // historical bracket lookup migration notice should be visible
    expect(screen.getByText(/Historical bracket lookup has moved/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open Historical Brackets/i })).toBeInTheDocument();

    // expand accordion to load bracket
    const matches = screen.getAllByText(/Playoff Bracket/i);
    expect(matches.length).toBeGreaterThan(1);
    matches[1].click();

    await waitFor(() => {
      expect(screen.getByText(/m1/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Wildcard Round/i)).toBeInTheDocument();
  });

  test('renders league name in sub-header once loaded', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url.startsWith('/playoffs/seasons')) {
        return Promise.resolve({ data: [2026] });
      }
      if (url.startsWith('/playoffs/bracket')) {
        return Promise.resolve({ data: { championship: [], consolation: [] } });
      }
      return Promise.resolve({ data: {} });
    });
    apiClient.post.mockResolvedValue({ data: { ok: true } });

    const setSubHeader = vi.fn();
    render(
      <MemoryRouter>
        <PlayoffBracket username="alice" leagueId={1} setSubHeader={setSubHeader} />
      </MemoryRouter>
    );

    // once league name loads, setSubHeader should include it
    await waitFor(() =>
      expect(setSubHeader).toHaveBeenCalledWith(expect.stringContaining('The Big Show'))
    );
  });

  test('hides toilet bowl view when consolation is disabled', async () => {
    const bracketData = {
      championship: [
        {
          match_id: 'm1',
          round: 1,
          is_bye: false,
          team_1_id: 1,
          team_2_id: 2,
          winner_to: 'r2_m1',
        },
      ],
      consolation: [],
      seeding_policy: {
        playoff_consolation: false,
        round_labels: {
          championship: { '1': 'Semifinal' },
          consolation: {},
        },
      },
    };

    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url.startsWith('/playoffs/seasons')) {
        return Promise.resolve({ data: [2026] });
      }
      if (url.startsWith('/playoffs/bracket')) {
        return Promise.resolve({ data: bracketData });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
    apiClient.post.mockResolvedValue({ data: { ok: true } });

    render(
      <MemoryRouter>
        <PlayoffBracket username="alice" leagueId={1} setSubHeader={() => {}} />
      </MemoryRouter>
    );

    const matches = screen.getAllByText(/Playoff Bracket/i);
    matches[1].click();

    await waitFor(() => {
      expect(screen.getByText(/m1/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Semifinal/i)).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /Toilet Bowl/i })).not.toBeInTheDocument();
  });
});
