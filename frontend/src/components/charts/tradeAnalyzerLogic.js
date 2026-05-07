import VALUATION_CONFIG from '@/config/valuation.json';

const T = VALUATION_CONFIG.trend_coefficient;       // 0.35
const V = VALUATION_CONFIG.volatility_coefficient;  // 0.20
const R = VALUATION_CONFIG.risk_coefficient;        // 1.5
export const BENCH_MULTIPLIER = VALUATION_CONFIG.bench_multiplier;
const BYE_PENALTY = VALUATION_CONFIG.bye_penalty;
const CASH_TIERS = VALUATION_CONFIG.cash_tiers;

export function toNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function normalizePosition(position) {
  const pos = String(position || '').toUpperCase();
  return pos === 'DEF' ? 'DST' : pos;
}

export function deriveTrendAdjustment(player) {
  const trendDirect = toNumber(player?.trend_adjustment, NaN);
  if (Number.isFinite(trendDirect)) return trendDirect;

  const recent = toNumber(player?.last_3_avg_points, NaN);
  const baseline = toNumber(player?.season_avg_points, NaN);
  if (Number.isFinite(recent) && Number.isFinite(baseline)) {
    return (recent - baseline) * T;
  }

  return 0;
}

export function deriveVolatilityPenalty(player) {
  const volatilityDirect = toNumber(player?.volatility_penalty, NaN);
  if (Number.isFinite(volatilityDirect)) return Math.max(0, volatilityDirect);

  const stdDev = toNumber(player?.points_stddev, toNumber(player?.volatility_index, 0));
  return Math.max(0, stdDev * V);
}

export function deriveRiskPenalty(player) {
  const riskDirect = toNumber(player?.risk_penalty, NaN);
  if (Number.isFinite(riskDirect)) return Math.max(0, riskDirect);

  const riskScore = toNumber(player?.risk_score, toNumber(player?.injury_risk, 0));
  return Math.max(0, riskScore * R);
}

export function computePlayerValue(player) {
  const ros = toNumber(player?.ros_projection, toNumber(player?.projected_points, 0));
  const trend = deriveTrendAdjustment(player);
  const volatilityPenalty = deriveVolatilityPenalty(player);
  const riskPenalty = deriveRiskPenalty(player);
  const byePenalty = player?.bye_week ? BYE_PENALTY : 0;
  const value = Number((ros + trend - volatilityPenalty - riskPenalty - byePenalty).toFixed(2));

  if (typeof import.meta !== 'undefined' && import.meta.env?.DEV) {
    console.debug('[valuation]', {
      player: player?.player_name ?? player?.name ?? '(unknown)',
      ros,
      trend,
      volatilityPenalty,
      riskPenalty,
      byePenalty,
      value,
    });
  }

  return value;
}

export function computeLineupAdjustedValue(player) {
  const base = computePlayerValue(player);
  const multiplier = player?.is_starter ? 1 : BENCH_MULTIPLIER;
  return Number((base * multiplier).toFixed(2));
}

export function summarizeTradeSide(players = []) {
  return Number(
    players
      .reduce((sum, player) => sum + computeLineupAdjustedValue(player), 0)
      .toFixed(2)
  );
}

export function computeOutgoingLossWithReplacement(outgoingPlayers = [], fullRoster = []) {
  const outgoingIds = new Set(outgoingPlayers.map((player) => player?.player_id));
  const replacementPool = fullRoster.filter((player) => {
    const playerId = player?.player_id;
    return playerId != null && !outgoingIds.has(playerId);
  });
  const usedReplacementIds = new Set();

  const starters = outgoingPlayers
    .filter((player) => player?.is_starter)
    .sort((a, b) => computePlayerValue(b) - computePlayerValue(a));
  const benchOutgoing = outgoingPlayers.filter((player) => player && !player?.is_starter);

  let totalLoss = 0;

  starters.forEach((player) => {
    if (!player) return;
    const starterValue = computePlayerValue(player);

    const outgoingPos = normalizePosition(player.position);
    const replacement = replacementPool
      .filter((candidate) => {
        if (!candidate) return false;
        if (usedReplacementIds.has(candidate.player_id)) return false;
        return normalizePosition(candidate.position) === outgoingPos;
      })
      .sort((a, b) => {
        const byValue = computePlayerValue(b) - computePlayerValue(a);
        if (byValue !== 0) return byValue;
        return toNumber(a?.player_id, Number.MAX_SAFE_INTEGER)
          - toNumber(b?.player_id, Number.MAX_SAFE_INTEGER);
      })[0];

    if (replacement?.player_id != null) {
      usedReplacementIds.add(replacement.player_id);
    }

    const replacementValue = replacement ? computePlayerValue(replacement) : 0;
    totalLoss += Math.max(0, starterValue - replacementValue);
  });

  benchOutgoing.forEach((player) => {
    totalLoss += computeLineupAdjustedValue(player);
  });

  return Number(totalLoss.toFixed(2));
}

export function computeNetLineupImpact({ incomingPlayers = [], outgoingPlayers = [], fullRoster = [] }) {
  const incomingGain = summarizeTradeSide(incomingPlayers);
  const outgoingLoss = computeOutgoingLossWithReplacement(outgoingPlayers, fullRoster);
  return Number((incomingGain - outgoingLoss).toFixed(2));
}

export function gradeForDelta(delta) {
  const abs = Math.abs(delta);
  if (abs <= 2) return ['A', 'A'];
  if (abs <= 5) return delta > 0 ? ['A', 'B'] : ['B', 'A'];
  if (abs <= 10) return delta > 0 ? ['B', 'C'] : ['C', 'B'];
  if (abs <= 15) return delta > 0 ? ['B', 'D'] : ['D', 'B'];
  return delta > 0 ? ['A', 'F'] : ['F', 'A'];
}

export function buildCashRecommendation(delta) {
  const abs = Math.abs(delta);
  for (const tier of CASH_TIERS) {
    if (tier.scale === null) continue;
    if (abs > tier.min_diff && (tier.max_diff === null || abs <= tier.max_diff)) {
      return {
        amount: Math.round(abs * tier.scale),
        tier: tier.label,
        explanation: tier.explanation,
      };
    }
  }
  return null;
}
