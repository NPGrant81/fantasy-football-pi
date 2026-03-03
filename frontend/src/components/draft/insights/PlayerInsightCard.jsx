import {
  confidenceBand,
  confidenceFromRisk,
  riskLabel,
  tierTone,
} from './insightVocabulary';

export default function PlayerInsightCard({
  recommendation,
  bidAmount,
}) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">
        Player-Level Insights
      </div>
      {!recommendation ? (
        <div className="mt-2 text-xs text-slate-500">
          Select a draftable player to view recommended bid, confidence band, and value signals.
        </div>
      ) : (
        <>
          <div className="mt-1 text-sm font-semibold text-emerald-200">
            {recommendation.player_name}
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-300">
            <div title="Model-recommended max bid after budget-aware capping.">
              <div className="text-slate-500">Recommended Bid</div>
              <div className="font-semibold text-emerald-300">
                ${Number(recommendation.recommended_bid || 0).toFixed(2)}
              </div>
            </div>
            <div title="Confidence is inversely related to risk score.">
              <div className="text-slate-500">Confidence</div>
              <div className="font-semibold">
                {confidenceFromRisk(recommendation.risk_score).toFixed(0)}%
              </div>
            </div>
            <div title="Model output score for comparative value.">
              <div className="text-slate-500">Value Score</div>
              <div className="font-semibold">
                {Number(recommendation.value_score || 0).toFixed(2)}
              </div>
            </div>
            <div title="Tier-based simplification of value score.">
              <div className="text-slate-500">Value Tier</div>
              <div className={`font-semibold ${tierTone(recommendation.tier)}`}>
                {recommendation.tier || 'C'}
              </div>
            </div>
          </div>

          <div className="mt-3 rounded border border-slate-800 p-2 text-xs text-slate-300">
            <div className="mb-1 text-slate-500" title="Range estimated from risk-adjusted uncertainty.">
              Confidence Band
            </div>
            {(() => {
              const band = confidenceBand(
                recommendation.recommended_bid,
                recommendation.risk_score
              );
              return (
                <div className="font-mono text-emerald-300">
                  ${band.low.toFixed(2)} - ${band.high.toFixed(2)}
                </div>
              );
            })()}
          </div>

          <div className="mt-2 rounded border border-slate-800 p-2 text-xs">
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
                  <div className="mb-1 text-slate-500" title="Current bid relative to recommendation.">
                    Live Bidding Pressure
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded bg-slate-800">
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
                  <div className="mt-1 text-[11px] text-slate-400">
                    {pressure}% of recommended bid
                  </div>
                  <div className="mt-2 font-semibold">
                    {bargain
                      ? 'BargainFlag: Bargain opportunity'
                      : overpriced
                      ? 'BargainFlag: Overpriced at current pressure'
                      : 'BargainFlag: Fair market range'}
                  </div>
                  <div className="mt-1 text-slate-400">
                    Risk: {riskLabel(recommendation.risk_score)} ({Number(
                      recommendation.risk_score || 0
                    ).toFixed(1)})
                  </div>
                </>
              );
            })()}
          </div>

          {(recommendation.flags || []).includes('high-risk') ? (
            <div className="mt-2 rounded border border-rose-900 bg-rose-950/40 px-2 py-1 text-xs text-rose-300">
              Low confidence fallback: volatility is elevated; consider wider bid tolerance.
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
