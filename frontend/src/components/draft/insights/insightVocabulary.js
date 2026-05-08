/**
 * UX Decision Hierarchy: classify each insight by how essential it is for
 * time-sensitive draft decisions.
 *
 *   MUST_KNOW  – displayed prominently, always visible
 *   SHOULD_KNOW – displayed by default but collapsible
 *   COULD_KNOW  – available on demand (tooltip / expand)
 */
export const UX_PRIORITY = {
  RECOMMENDED_BID: 'MUST_KNOW',
  CONFIDENCE_BAND: 'MUST_KNOW',
  BARGAIN_FLAG: 'MUST_KNOW',
  VALUE_TIER: 'SHOULD_KNOW',
  RISK_SCORE: 'SHOULD_KNOW',
  SCARCITY: 'SHOULD_KNOW',
  BIDDING_PRESSURE: 'SHOULD_KNOW',
  VALUE_SCORE: 'COULD_KNOW',
  STRATEGY_ALIGNMENT: 'SHOULD_KNOW',
  INFLATION_INDEX: 'COULD_KNOW',
};

/**
 * Severity levels for alert/callout components.
 *
 *   CRITICAL  – breaks strategy; shown in rose
 *   WARNING   – risk signal; shown in amber
 *   INFO      – contextual note; shown in slate/cyan
 *   NEUTRAL   – no action required
 */
export const INSIGHT_SEVERITY = {
  CRITICAL: 'critical',
  WARNING: 'warning',
  INFO: 'info',
  NEUTRAL: 'neutral',
};

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

/**
 * Map a risk score to a confidence rendering tier:
 *
 *   'high'     – confident recommendation; use assertive language
 *   'moderate' – reasonable signal; note uncertainty
 *   'low'      – noisy signal; use caution framing
 *   'degraded' – fallback / no-data path; suppress assertiveness
 */
export function confidenceTier(riskScore) {
  const score = Number(riskScore ?? 100);
  if (score < 30) return 'high';
  if (score < 55) return 'moderate';
  if (score < 80) return 'low';
  return 'degraded';
}

/**
 * Return the Tailwind classes for an INSIGHT_SEVERITY alert box.
 */
export function severityClasses(severity) {
  switch (severity) {
    case INSIGHT_SEVERITY.CRITICAL:
      return 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300';
    case INSIGHT_SEVERITY.WARNING:
      return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300';
    case INSIGHT_SEVERITY.INFO:
      return 'border-cyan-200 bg-cyan-50 text-cyan-800 dark:border-cyan-900 dark:bg-cyan-950/30 dark:text-cyan-300';
    default:
      return 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-950/30 dark:text-slate-400';
  }
}

/**
 * Derive severity level for strategy-break alerts.
 * Returns INSIGHT_SEVERITY constant or null if no alert.
 */
export function strategyBreakSeverity({ exceedsPosCap, mostBehindPosition } = {}) {
  if (exceedsPosCap) return INSIGHT_SEVERITY.CRITICAL;
  if (mostBehindPosition?.delta < -1) return INSIGHT_SEVERITY.WARNING;
  return null;
}

/**
 * Generate a one-sentence plain-language explainability snippet for a
 * recommendation.  Returns null when there is insufficient context.
 *
 * @param {object} recommendation – model recommendation object
 * @param {object} [ownerContext]  – optional { budget, spentAtPosition }
 */
export function explainRecommendation(recommendation, ownerContext = {}) {
  if (!recommendation) return null;

  const tier = confidenceTier(recommendation.risk_score);
  const rec = Number(recommendation.recommended_bid || 0);
  const pos = normalizePos(recommendation.position || '');
  const name = recommendation.player_name || 'This player';

  const budgetNote =
    ownerContext.budget != null && rec > 0
      ? ownerContext.budget > 0
        ? ` (${Math.round((rec / ownerContext.budget) * 100)}% of remaining budget)`
        : ' (remaining budget exhausted)'
      : '';

  if (tier === 'degraded') {
    return `${name}: model confidence is too low to make a reliable bid recommendation — consider market price only.`;
  }
  if (tier === 'low') {
    return `${name}: high volatility at ${pos}; recommended bid of $${rec.toFixed(0)}${budgetNote} carries meaningful uncertainty — widen your bid tolerance.`;
  }
  if (tier === 'moderate') {
    return `${name}: solid ${pos} value at $${rec.toFixed(0)}${budgetNote}; model sees moderate risk — stay near the recommendation.`;
  }
  return `${name}: strong ${pos} value signal — recommended bid of $${rec.toFixed(0)}${budgetNote} with high model confidence.`;
}
