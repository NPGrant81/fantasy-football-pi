import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import apiClient from '../src/api/client';
import BracketAccordion from '../src/pages/home/components/BracketAccordion';

describe('BracketAccordion', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('renders bracket fallback source and warnings', async () => {
    const user = userEvent.setup();
    apiClient.post.mockResolvedValue({ data: {} });
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({
          data: [
            { id: 1, team_name: 'Alpha' },
            { id: 4, team_name: 'Delta' },
          ],
        });
      }
      if (url === '/playoffs/bracket?league_id=1&season=2026') {
        return Promise.resolve({
          data: {
            championship: [
              {
                match_id: 'm1',
                round: 1,
                team_1_id: 1,
                team_2_id: 4,
                team_1_seed: 1,
                team_2_seed: 4,
              },
            ],
            consolation: [],
            seeding_policy: {
              division_winners_top_seeds: true,
              wildcards_by_overall_record: true,
              playoff_consolation: false,
              tiebreak_chain: ['overall_record', 'points_for'],
              round_labels: {
                championship: { '1': 'Semifinals' },
              },
            },
            meta: {
              source: 'matches_fallback',
              is_partial: true,
              warnings: ['Historical season snapshot is unavailable; bracket rendered from playoff match rows and current league settings where season-specific settings were not captured.'],
            },
          },
        });
      }
      if (url === '/playoffs/seasons?league_id=1') {
        return Promise.resolve({ data: [2026, 2025] });
      }
      return Promise.reject(new Error(`Unknown URL: ${url}`));
    });

    render(<BracketAccordion leagueId={1} />);

    await user.click(screen.getByText(/playoff bracket/i));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/playoffs/generate', {
        league_id: 1,
        season: 2026,
      });
    });

    expect(await screen.findByText(/Bracket Source/i)).toBeInTheDocument();
    expect(screen.getByText(/matches fallback/i)).toBeInTheDocument();
    expect(screen.getByText(/Partial Data/i)).toBeInTheDocument();
    expect(screen.getByText(/Historical season snapshot is unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/Division Winners Top Seeds/i)).toBeInTheDocument();
    expect(screen.getByText(/Alpha/i)).toBeInTheDocument();
    expect(screen.getByText(/Delta/i)).toBeInTheDocument();
  });

  test('renders default source label when meta source is missing', async () => {
    const user = userEvent.setup();
    apiClient.post.mockResolvedValue({ data: {} });
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/owners?league_id=7') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/playoffs/bracket?league_id=7&season=2026') {
        return Promise.resolve({
          data: {
            championship: [],
            consolation: [],
            seeding_policy: {
              playoff_consolation: false,
              tiebreak_chain: [],
              round_labels: { championship: {} },
            },
            meta: {
              is_partial: false,
              warnings: [],
            },
          },
        });
      }
      if (url === '/playoffs/seasons?league_id=7') {
        return Promise.resolve({ data: [2026] });
      }
      return Promise.reject(new Error(`Unknown URL: ${url}`));
    });

    render(<BracketAccordion leagueId={7} />);

    await user.click(screen.getByText(/playoff bracket/i));

    expect(await screen.findByText(/Bracket Source/i)).toBeInTheDocument();
    expect(screen.getByText(/Live data/i)).toBeInTheDocument();
    expect(screen.queryByText(/Partial Data/i)).not.toBeInTheDocument();
  });
});