export const BENCH_MULTIPLIER = 0.6;

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
    return (recent - baseline) * 0.35;
  }

  return 0;
}

export function deriveVolatilityPenalty(player) {
  const volatilityDirect = toNumber(player?.volatility_penalty, NaN);
  if (Number.isFinite(volatilityDirect)) return Math.max(0, volatilityDirect);

  const stdDev = toNumber(player?.points_stddev, toNumber(player?.volatility_index, 0));
  return Math.max(0, stdDev * 0.25);
}

export function deriveRiskPenalty(player) {
  const riskDirect = toNumber(player?.risk_penalty, NaN);
  if (Number.isFinite(riskDirect)) return Math.max(0, riskDirect);

  const riskScore = toNumber(player?.risk_score, toNumber(player?.injury_risk, 0));
  return Math.max(0, riskScore * 0.4);
}

export function computePlayerValue(player) {
  const ros = toNumber(player?.ros_projection, toNumber(player?.projected_points, 0));
  const trend = deriveTrendAdjustment(player);
  const volatilityPenalty = deriveVolatilityPenalty(player);
  const riskPenalty = deriveRiskPenalty(player);
  const byePenalty = player?.bye_week ? 0.15 : 0;

  return Number((ros + trend - volatilityPenalty - riskPenalty - byePenalty).toFixed(2));
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
  if (abs <= 10) return null;

  if (abs <= 15) {
    return {
      amount: Math.round(abs * 0.45),
      tier: 'Slightly Unbalanced',
      explanation: 'Adjustment recommended because value swing is above 10 points.',
    };
  }
  if (abs <= 25) {
    return {
      amount: Math.round(abs * 0.6),
      tier: 'Moderately Unbalanced',
      explanation: 'Cash can rebalance immediate starter impact and depth tradeoff.',
    };
  }
  return {
    amount: Math.round(abs * 0.75),
    tier: 'Highly Unbalanced',
    explanation: 'Large imbalance: strong recommendation to include draft cash.',
  };
}
