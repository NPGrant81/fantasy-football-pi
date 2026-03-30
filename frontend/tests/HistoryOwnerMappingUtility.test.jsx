import { fireEvent, render, screen, waitFor } from '../src/setupTests';
import { vi } from 'vitest';
import apiClient from '@/api/client';
import HistoryOwnerMappingUtility from '@/pages/commissioner/HistoryOwnerMappingUtility';

describe('HistoryOwnerMappingUtility hardening', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    localStorage.setItem('fantasyLeagueId', '60');
  });

  test('keeps mapping tools usable when owner-gap-report load fails', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/owners?league_id=60')) {
        return Promise.resolve({ data: [{ id: 1, username: 'owner-a', team_name: 'Team A' }] });
      }
      if (url === '/leagues/60/history/team-owner-map') {
        return Promise.resolve({ data: { mappings: [] } });
      }
      if (url === '/leagues/60/history/unmapped-series-keys') {
        return Promise.resolve({ data: { unmapped: [], mapped: [] } });
      }
      if (url.startsWith('/leagues/60/history/owner-gap-report')) {
        return Promise.reject({ response: { data: { detail: 'gap endpoint unavailable' } } });
      }
      return Promise.resolve({ data: [] });
    });

    render(<HistoryOwnerMappingUtility />);

    await waitFor(() => {
      expect(screen.getByText(/Owner gap diagnostics unavailable/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/gap endpoint unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry Diagnostics Load/i })).toBeInTheDocument();
    expect(screen.getByText(/Manual Mapping/i)).toBeInTheDocument();
  });

  test('renders diagnostics quality notes when metadata reports malformed rows and truncation', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/owners?league_id=60')) {
        return Promise.resolve({ data: [{ id: 1, username: 'owner-a', team_name: 'Team A' }] });
      }
      if (url === '/leagues/60/history/team-owner-map') {
        return Promise.resolve({ data: { mappings: [] } });
      }
      if (url === '/leagues/60/history/unmapped-series-keys') {
        return Promise.resolve({ data: { unmapped: [], mapped: [] } });
      }
      if (url.startsWith('/leagues/60/history/owner-gap-report')) {
        return Promise.resolve({
          data: {
            league_id: 60,
            summary: {
              placeholder_mapping_count: 0,
              unresolved_match_team_count: 10,
              unresolved_series_team_count: 20,
              unresolved_series_source_token_count: 5,
              season_count: 12,
            },
            metadata: {
              response_limits: { detail_limit: 6, season_limit: 5 },
              truncated: {
                placeholder_mappings: false,
                unresolved_match_teams: true,
                unresolved_series_teams: true,
                unresolved_series_source_tokens: false,
                seasons: true,
              },
              ignored_malformed_row_count: {
                match_records: 2,
                series_records: 1,
              },
            },
            seasons: [],
            placeholder_mappings: [],
            unresolved_match_teams: [],
            unresolved_series_teams: [],
            unresolved_series_source_tokens: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    render(<HistoryOwnerMappingUtility />);

    await waitFor(() => {
      expect(screen.getByText(/Diagnostics quality notes/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Ignored malformed rows: matchup 2, series 1./i)).toBeInTheDocument();
    expect(screen.getByText(/Response is truncated by server limits/i)).toBeInTheDocument();
  });

  test('shows and toggles Show All Rows control when unresolved row volume is high', async () => {
    const unresolvedRows = Array.from({ length: 25 }, (_, index) => ({
      season: 2026,
      team_name: `Ghost Team ${index + 1}`,
      team_name_key: `ghost team ${index + 1}`,
      side: 'away',
      occurrence_count: 1,
    }));

    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/owners?league_id=60')) {
        return Promise.resolve({ data: [{ id: 1, username: 'owner-a', team_name: 'Team A' }] });
      }
      if (url === '/leagues/60/history/team-owner-map') {
        return Promise.resolve({ data: { mappings: [] } });
      }
      if (url === '/leagues/60/history/unmapped-series-keys') {
        return Promise.resolve({ data: { unmapped: [], mapped: [] } });
      }
      if (url.startsWith('/leagues/60/history/owner-gap-report')) {
        return Promise.resolve({
          data: {
            league_id: 60,
            summary: {
              placeholder_mapping_count: 0,
              unresolved_match_team_count: 25,
              unresolved_series_team_count: 0,
              unresolved_series_source_token_count: 0,
              season_count: 1,
            },
            metadata: {
              response_limits: { detail_limit: 250, season_limit: 50 },
              truncated: {
                placeholder_mappings: false,
                unresolved_match_teams: false,
                unresolved_series_teams: false,
                unresolved_series_source_tokens: false,
                seasons: false,
              },
              ignored_malformed_row_count: {
                match_records: 0,
                series_records: 0,
              },
            },
            seasons: [{ season: 2026, occurrence_count: 25 }],
            placeholder_mappings: [],
            unresolved_match_teams: unresolvedRows,
            unresolved_series_teams: [],
            unresolved_series_source_tokens: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });

    render(<HistoryOwnerMappingUtility />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Show All Rows \(25\)/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Show All Rows \(25\)/i }));
    expect(screen.getByRole('button', { name: /Show Top Rows/i })).toBeInTheDocument();
  });
});
