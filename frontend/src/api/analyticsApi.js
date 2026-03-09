import { getJson } from '@api/fetching';

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

export function fetchRosterStrengthAnalytics(leagueId, ownerId) {
  return getJson('/analytics/roster-strength', {
    params: { league_id: leagueId, owner_id: ownerId },
    retries: 1,
  });
}

export function fetchRivalryAnalytics(leagueId) {
  return getJson(`/analytics/league/${leagueId}/rivalry`, { retries: 1 });
}
