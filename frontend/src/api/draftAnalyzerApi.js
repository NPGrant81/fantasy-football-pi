import { getJson, postJson } from '@api/fetching';

const NAME_SUFFIXES = new Set(['jr', 'sr', 'ii', 'iii', 'iv', 'v']);

function normalizeText(value) {
  return String(value || '').trim().toLowerCase();
}

function normalizeNameForDedupe(value) {
  const compact = normalizeText(value).replace(/[^a-z0-9]+/g, ' ').trim();
  let tokens = compact ? compact.split(/\s+/) : [];
  if (tokens.length > 0 && NAME_SUFFIXES.has(tokens[tokens.length - 1])) {
    tokens.pop();
  }
  if (tokens.length >= 2) {
    let idx = 0;
    while (idx < tokens.length && tokens[idx].length === 1) {
      idx += 1;
    }
    if (idx >= 2) {
      tokens = [tokens.slice(0, idx).join(''), ...tokens.slice(idx)];
    }
  }
  return tokens.join(' ');
}

function buildFallbackPlayerKey(player) {
  return [
    normalizeNameForDedupe(player?.name),
    normalizeText(player?.position),
  ].join('|');
}

function dedupePlayersForUi(players) {
  const list = Array.isArray(players) ? players : [];
  const selected = new Map();

  for (const player of list) {
    const key = buildFallbackPlayerKey(player);
    const current = selected.get(key);
    const playerHasExternal = Boolean(player?.gsis_id || player?.espn_id);
    const currentHasExternal = Boolean(current?.gsis_id || current?.espn_id);
    const playerIsActiveTeam = normalizeText(player?.nfl_team) !== 'fa';
    const currentIsActiveTeam = normalizeText(current?.nfl_team) !== 'fa';

    const shouldReplace =
      !current ||
      (playerHasExternal && !currentHasExternal) ||
      (playerHasExternal === currentHasExternal && playerIsActiveTeam && !currentIsActiveTeam) ||
      (playerHasExternal === currentHasExternal && playerIsActiveTeam === currentIsActiveTeam && Number(player?.id || 0) > Number(current?.id || 0));

    if (shouldReplace) {
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
