export const POSITION_CAPS = {
  QB: 2,
  RB: 5,
  WR: 5,
  TE: 2,
  DEF: 1,
  K: 1,
};

export const STRATEGY_MAX_SPEND_SHARE = {
  QB: 0.15,
  RB: 0.32,
  WR: 0.32,
  TE: 0.12,
  DEF: 0.05,
  K: 0.04,
};

export const INSIGHT_VOCABULARY_HINT =
  'Use this insight vocabulary consistently when relevant: ValueScore, ValueTier, RecommendedBid, ConfidenceBand, RiskScore, Scarcity, BargainFlag, StrategyAlignment, BiddingPressure, InflationIndex.';

export function normalizePos(value) {
  return String(value || '')
    .toUpperCase()
    .replace('D/ST', 'DEF')
    .replace('DST', 'DEF');
}

export function tierTone(tier) {
  const normalized = String(tier || 'C').toUpperCase();
  if (normalized === 'S') return 'text-emerald-300';
  if (normalized === 'A') return 'text-cyan-300';
  if (normalized === 'B') return 'text-blue-300';
  if (normalized === 'C') return 'text-amber-300';
  return 'text-rose-300';
}

export function riskLabel(riskScore) {
  const score = Number(riskScore || 0);
  if (score >= 70) return 'High';
  if (score >= 45) return 'Moderate';
  return 'Low';
}

export function confidenceFromRisk(riskScore) {
  const score = Number(riskScore || 0);
  return Math.max(5, Math.min(95, 100 - score));
}

export function confidenceBand(recommendedBid, riskScore) {
  const rec = Number(recommendedBid || 1);
  const spreadPct = 0.08 + Number(riskScore || 0) / 250;
  const low = Math.max(1, rec * (1 - spreadPct));
  const high = rec * (1 + spreadPct);
  return {
    low: Number(low.toFixed(2)),
    high: Number(high.toFixed(2)),
  };
}
