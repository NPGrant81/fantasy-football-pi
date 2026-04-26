import apiClient from '@api/client';

// ── Trade Window Settings ───────────────────────────────────────────────────

export async function fetchTradeWindowSettings(leagueId) {
  const res = await apiClient.get(`/trades/leagues/${leagueId}/settings/trade-window`);
  return res.data;
}

export async function saveTradeWindowSettings(leagueId, payload) {
  const res = await apiClient.put(`/trades/leagues/${leagueId}/settings/trade-window`, payload);
  return res.data;
}

// ── Pending queue (commissioner) ────────────────────────────────────────────

export async function fetchPendingTrades(leagueId) {
  const res = await apiClient.get(`/trades/leagues/${leagueId}/pending-v2`);
  const data = res.data;
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.trades)) return data.trades;
  if (Array.isArray(data?.items)) return data.items;
  return [];
}

export async function fetchTradeDetail(leagueId, tradeId) {
  const res = await apiClient.get(`/trades/leagues/${leagueId}/${tradeId}-v2`);
  return res.data;
}

export async function fetchTradeHistory(leagueId, tradeId) {
  const res = await apiClient.get(`/trades/leagues/${leagueId}/${tradeId}/history-v2`);
  const data = res.data;
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.events)) return data.events;
  return [];
}

export async function approveTrade(leagueId, tradeId, comments = '') {
  const res = await apiClient.post(`/trades/leagues/${leagueId}/${tradeId}/approve-v2`, {
    commissioner_comments: comments,
  });
  return res.data;
}

export async function rejectTrade(leagueId, tradeId, comments = '') {
  const res = await apiClient.post(`/trades/leagues/${leagueId}/${tradeId}/reject-v2`, {
    commissioner_comments: comments,
  });
  return res.data;
}

// ── Trade submission ────────────────────────────────────────────────────────

export async function submitTrade(leagueId, payload) {
  const res = await apiClient.post(`/trades/leagues/${leagueId}/submit-v2`, payload);
  return res.data;
}

// ── Roster helpers ──────────────────────────────────────────────────────────

export async function fetchTeamRoster(leagueId, teamId) {
  const res = await apiClient.get(`/team/${teamId}`, { params: { league_id: leagueId } });
  return Array.isArray(res.data) ? res.data : (res.data?.players ?? []);
}

export async function fetchLeagueTeams(leagueId) {
  const res = await apiClient.get('/leagues/owners', { params: { league_id: leagueId } });
  return Array.isArray(res.data) ? res.data : [];
}
