import { getJson } from '@api/fetching';

export function fetchCurrentUser() {
  return getJson('/auth/me', { retries: 0 });
}

export function fetchLeagueById(leagueId) {
  return getJson(`/leagues/${leagueId}`, { retries: 1 });
}

export function fetchLeagueOwners(leagueId) {
  return getJson('/leagues/owners', {
    params: { league_id: leagueId },
    retries: 1,
  });
}
