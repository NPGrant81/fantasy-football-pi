/* ignore-breakpoints */
import {
  confidenceBand,
  confidenceFromRisk,
  confidenceTier,
  explainRecommendation,
  INSIGHT_SEVERITY,
  normalizePos,
  riskLabel,
  severityClasses,
  tierTone,
} from './insightVocabulary';

/**
 * PlayerInsightCard — player-level ML insights panel.
 *
 * Props:
 *   recommendation     – model recommendation object for the selected player
 *   bidAmount          – current live bid amount (for pressure bar)
 *   scarcityByPosition – array of { position, scarcity } from draftDynamics
 *   ownerContext       – optional { budget } for explainability snippet
 */
export default function PlayerInsightCard({
  recommendation,
  bidAmount,
  scarcityByPosition = [],
  ownerContext = {},
}) {
  return (
    <div className="rounded-md border border-slate-300 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">
        Player-Level Insights
      </div>
      {!recommendation ? (
        <div className="mt-2 text-xs text-slate-500 dark:text-slate-500">
          Select a draftable player to view recommended bid, confidence band, and value signals.
        </div>
      ) : (
        <>
          {/* Explainability snippet — must-know for decision context */}
          {(() => {
            const snippet = explainRecommendation(recommendation, ownerContext);
            const tier = confidenceTier(recommendation.risk_score);
            const snippetClasses =
              tier === 'degraded'
                ? 'rounded border border-rose-300 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/40 px-2 py-1 text-xs text-rose-800 dark:text-rose-200'
                : tier === 'low'
                ? 'rounded border border-amber-300 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 px-2 py-1 text-xs text-amber-800 dark:text-amber-200'
                : 'rounded border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 px-2 py-1 text-xs text-slate-700 dark:text-slate-300';
            return snippet ? (
              <div className={`mt-2 ${snippetClasses}`}>{snippet}</div>
            ) : null;
          })()}

          <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-emerald-200">
            {recommendation.player_name}
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-700 dark:text-slate-300">
            <div title="Model-recommended max bid after budget-aware capping.">
              <div className="text-slate-500 dark:text-slate-500">Recommended Bid</div>
              <div className="font-semibold text-emerald-700 dark:text-emerald-300">
                ${Number(recommendation.recommended_bid || 0).toFixed(2)}
              </div>
            </div>
            <div title="Confidence is inversely related to risk score.">
              <div className="text-slate-500 dark:text-slate-500">Confidence</div>
              {(() => {
                const tier = confidenceTier(recommendation.risk_score);
                const pct = confidenceFromRisk(recommendation.risk_score).toFixed(0);
                const color =
                  tier === 'high'
                    ? 'text-emerald-700 dark:text-emerald-300'
                    : tier === 'moderate'
                    ? 'text-blue-700 dark:text-blue-300'
                    : tier === 'low'
                    ? 'text-amber-700 dark:text-amber-300'
                    : 'text-rose-700 dark:text-rose-300';
                return <div className={`font-semibold ${color}`}>{pct}%</div>;
              })()}
            </div>
            <div title="Model output score for comparative value.">
              <div className="text-slate-500 dark:text-slate-500">Value Score</div>
              <div className="font-semibold">
                {Number(recommendation.value_score || 0).toFixed(2)}
              </div>
            </div>
            <div title="Tier-based simplification of value score.">
              <div className="text-slate-500 dark:text-slate-500">Value Tier</div>
              <div className={`font-semibold ${tierTone(recommendation.tier)}`}>
                {recommendation.tier || 'C'}
              </div>
            </div>
          </div>

          <div className="mt-3 rounded border border-slate-300 dark:border-slate-800 p-2 text-xs text-slate-700 dark:text-slate-300">
            <div className="mb-1 text-slate-500 dark:text-slate-500" title="Range estimated from risk-adjusted uncertainty.">
              Confidence Band
            </div>
            {(() => {
              const band = confidenceBand(
                recommendation.recommended_bid,
                recommendation.risk_score
              );
              return (
                <div className="font-mono text-emerald-700 dark:text-emerald-300">
                  ${band.low.toFixed(2)} – ${band.high.toFixed(2)}
                </div>
              );
            })()}
          </div>

          {/* Per-position scarcity indicator — should-know */}
          {(() => {
            const pos = normalizePos(recommendation.position || '');
            const scarcityRow = scarcityByPosition.find(
              (r) => normalizePos(r.position || '') === pos
            );
            if (!scarcityRow || !pos) return null;
            const pct = Math.min(100, Number(scarcityRow.scarcity || 0));
            const color =
              pct >= 80
                ? 'bg-rose-500'
                : pct >= 55
                ? 'bg-amber-500'
                : 'bg-emerald-500';
            const label =
              pct >= 80 ? 'Scarce' : pct >= 55 ? 'Moderate' : 'Available';
            return (
              <div className="mt-2 rounded border border-slate-300 dark:border-slate-800 p-2 text-xs">
                <div
                  className="mb-1 text-slate-500 dark:text-slate-500"
                  title={`Positional scarcity for ${pos}: remaining league demand vs available pool.`}
                >
                  Scarcity ({pos})
                </div>
                <div className="h-2 w-full overflow-hidden rounded bg-slate-200 dark:bg-slate-800">
                  <div className={`h-2 ${color}`} style={{ width: `${pct}%` }} />
                </div>
                <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                  {label} — {pct.toFixed(0)}% demand pressure
                </div>
              </div>
            );
          })()}

          <div className="mt-2 rounded border border-slate-300 dark:border-slate-800 p-2 text-xs">
            {(() => {
              const currentBidValue = Number(bidAmount || 0);
              const recommended = Number(recommendation.recommended_bid || 1);
              const predicted = Number(recommendation.predicted_value || 1);
              const bargain =
                currentBidValue > 0 && currentBidValue <= predicted * 0.9;
              const overpriced = currentBidValue > recommended * 1.1;
              const pressure = Math.min(
                100,
                Math.round((currentBidValue / Math.max(recommended, 1)) * 100)
              );
              return (
                <>
                  <div className="mb-1 text-slate-500 dark:text-slate-500" title="Current bid relative to recommendation.">
                    Live Bidding Pressure
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded bg-slate-200 dark:bg-slate-800">
                    <div
                      className={`h-2 ${
                        pressure >= 110
                          ? 'bg-rose-500'
                          : pressure >= 90
                          ? 'bg-amber-500'
                          : 'bg-emerald-500'
                      }`}
                      style={{ width: `${Math.min(100, pressure)}%` }}
                    />
                  </div>
                  <div className="mt-1 text-[11px] text-slate-400 dark:text-slate-400">
                    {pressure}% of recommended bid
                  </div>
                  <div className="mt-2 font-semibold text-slate-800 dark:text-slate-200">
                    {bargain
                      ? 'BargainFlag: Bargain opportunity'
                      : overpriced
                      ? 'BargainFlag: Overpriced at current pressure'
                      : 'BargainFlag: Fair market range'}
                  </div>
                  <div className="mt-1 text-slate-500 dark:text-slate-400">
                    Risk: {riskLabel(recommendation.risk_score)} ({Number(
                      recommendation.risk_score || 0
                    ).toFixed(1)})
                  </div>
                </>
              );
            })()}
          </div>

          {/* Confidence-degraded fallback callout */}
          {confidenceTier(recommendation.risk_score) === 'degraded' ? (
            <div className={`mt-2 rounded border px-2 py-1 text-xs ${severityClasses(INSIGHT_SEVERITY.CRITICAL)}`}>
              Model confidence is too low for a reliable bid; treat this as a rough
              estimate only and consider market price independently.
            </div>
          ) : confidenceTier(recommendation.risk_score) === 'low' ? (
            <div className={`mt-2 rounded border px-2 py-1 text-xs ${severityClasses(INSIGHT_SEVERITY.WARNING)}`}>
              Low confidence — volatility is elevated; consider wider bid tolerance.
            </div>
          ) : (recommendation.flags || []).includes('high-risk') ? (
            <div className={`mt-2 rounded border px-2 py-1 text-xs ${severityClasses(INSIGHT_SEVERITY.WARNING)}`}>
              Risk flag: volatility is elevated; consider wider bid tolerance.
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
