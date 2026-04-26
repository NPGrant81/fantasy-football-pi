import apiClient from '@api/client';

function isNotFound(error) {
  return Number(error?.response?.status || 0) === 404;
}

function fromLegacyLeagueSettings(data = {}) {
  const tradeEndAt = data.trade_deadline || null;
  const isActive = tradeEndAt ? new Date(tradeEndAt).getTime() > Date.now() : true;
  return {
    trade_start_at: null,
    trade_end_at: tradeEndAt,
    timezone: 'UTC',
    is_active: isActive,
  };
}

// ── Trade Window Settings ───────────────────────────────────────────────────

export async function fetchTradeWindowSettings(leagueId) {
  try {
    const res = await apiClient.get(`/trades/leagues/${leagueId}/settings/trade-window`);
    return res.data;
  } catch (error) {
    if (!isNotFound(error)) throw error;
    const legacy = await apiClient.get(`/leagues/${leagueId}/settings`);
    return fromLegacyLeagueSettings(legacy.data);
  }
}

export async function saveTradeWindowSettings(leagueId, payload) {
  try {
    const res = await apiClient.put(`/trades/leagues/${leagueId}/settings/trade-window`, payload);
    return res.data;
  } catch (error) {
    if (!isNotFound(error)) throw error;
    // Legacy fallback: only trade_deadline exists on older league settings schema.
    const legacyPayload = {
      trade_deadline: payload.is_active ? payload.trade_end_at : new Date().toISOString(),
    };
    const res = await apiClient.put(`/leagues/${leagueId}/settings`, legacyPayload);
    return fromLegacyLeagueSettings(res.data);
  }
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
