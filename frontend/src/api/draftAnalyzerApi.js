import { getJson, postJson } from '@api/fetching';

function normalizeText(value) {
  return String(value || '').trim().toLowerCase();
}

function buildFallbackPlayerKey(player) {
  return [
    normalizeText(player?.name),
    normalizeText(player?.position),
    normalizeText(player?.nfl_team),
  ].join('|');
}

function dedupePlayersForUi(players) {
  const list = Array.isArray(players) ? players : [];
  const selected = new Map();

  for (const player of list) {
    const hasStableId = player?.id !== null && player?.id !== undefined;
    const key = hasStableId ? `id:${player.id}` : `fallback:${buildFallbackPlayerKey(player)}`;
    const current = selected.get(key);
    if (!current || Number(player?.id || 0) > Number(current?.id || 0)) {
      selected.set(key, player);
    }
  }

  return Array.from(selected.values());
}

export function fetchCurrentUser() {
  return getJson('/auth/me', { retries: 0 });
}

export function fetchLeagueOwners(leagueId) {
  return getJson('/leagues/owners', {
    params: { league_id: leagueId },
    retries: 1,
  });
}

export function fetchAllPlayers() {
  return getJson('/players/', { retries: 1 }).then(dedupePlayersForUi);
}

export function fetchLeagueSettings(leagueId) {
  return getJson(`/leagues/${leagueId}/settings`, { retries: 1 });
}

export function fetchDraftHistory(sessionId) {
  return getJson('/draft/history', {
    params: { session_id: sessionId },
    retries: 1,
  });
}

export function fetchHistoricalRankings({ season, leagueId, ownerId, limit = 300 }) {
  const params = { season, league_id: leagueId, limit };
  if (ownerId) params.owner_id = ownerId;
  return getJson('/draft/rankings', { params, retries: 1 });
}

export function fetchModelPredictions(payload) {
  return postJson('/draft/model/predict', payload, { retries: 0 });
}

export function runDraftSimulation(payload) {
  return postJson('/draft/simulation', payload, { retries: 0 });
}

export function fetchPlayerSeasonDetails(playerId, season) {
  return getJson(`/players/${playerId}/season-details`, {
    params: { season },
    retries: 1,
  });
}

export function queryDraftAdvisor(payload) {
  return postJson('/advisor/draft-day/query', payload, { retries: 0 });
}
