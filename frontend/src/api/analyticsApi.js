import { getJson, postJson } from '@api/fetching';

export function resolveRows(payload) {
  if (payload && !Array.isArray(payload) && Array.isArray(payload.rows)) {
    return payload.rows;
  }
  return Array.isArray(payload) ? payload : [];
}

export function fetchDraftValueAnalytics(leagueId, season, limit = 80) {
  return getJson(`/analytics/league/${leagueId}/draft-value`, {
    params: { season, limit },
    retries: 1,
  });
}

export function fetchManagerEfficiencyLeaderboard(leagueId) {
  return getJson(`/analytics/league/${leagueId}/leaderboard`, { retries: 1 });
}

export function fetchManagerWeeklyStats(leagueId, managerId) {
  return getJson(`/analytics/league/${leagueId}/weekly-stats`, {
    params: { manager_id: managerId },
    retries: 1,
  });
}

export function fetchWeeklyMatchupsAnalytics(leagueId, season) {
  return getJson(`/analytics/league/${leagueId}/weekly-matchups`, {
    params: { season, start_week: 1, end_week: 17 },
    retries: 1,
  });
}

export function fetchPlayerHeatmapAnalytics(leagueId, season, limit = 8, weeks = 8) {
  return getJson(`/analytics/league/${leagueId}/player-heatmap`, {
    params: { season, limit, weeks },
    retries: 1,
  });
}

export function fetchPositionalHeatmapAnalytics(leagueId, season, profile = 'standard', streamPosition = 'WR') {
  return getJson(`/analytics/league/${leagueId}/positional-heatmap`, {
    params: {
      season,
      profile,
      stream_position: streamPosition,
    },
    retries: 1,
  });
}

export function fetchRosterStrengthAnalytics(leagueId, ownerId) {
  return getJson('/analytics/roster-strength', {
    params: { league_id: leagueId, owner_id: ownerId },
    retries: 1,
  });
}

export function fetchRivalryAnalytics(leagueId) {
  return getJson(`/analytics/league/${leagueId}/rivalry`, { retries: 1 });
}

export function fetchLuckIndexAnalytics(leagueId, season) {
  return getJson(`/analytics/league/${leagueId}/luck-index`, {
    params: { season },
    retries: 1,
  });
}

export function fetchPlayerConsistencyAnalytics(leagueId, season, limit = 20) {
  return getJson(`/analytics/league/${leagueId}/player-consistency`, {
    params: { season, limit },
    retries: 1,
  });
}

export function fetchWaiverOpportunitiesAnalytics(leagueId, season, position = null, limit = 30) {
  const params = { season, limit };
  if (position) params.position = position;
  return getJson(`/analytics/league/${leagueId}/waiver-opportunities`, {
    params,
    retries: 1,
  });
}

export function fetchInSeasonInsights(leagueId, ownerId, season, waiverLimit = 8, startSitLimit = 10) {
  return getJson(`/analytics/league/${leagueId}/in-season-insights`, {
    params: {
      owner_id: ownerId,
      season,
      waiver_limit: waiverLimit,
      start_sit_limit: startSitLimit,
    },
    retries: 1,
  });
}

export function askInSeasonAdvisor({ userQuery, username, leagueId, ownerId, season, inSeasonContext }) {
  return postJson('/advisor/in-season/query', {
    user_query: userQuery,
    username: username ?? null,
    league_id: leagueId ?? null,
    owner_id: ownerId ?? null,
    season: season ?? null,
    in_season_context: inSeasonContext ?? null,
  });
}
