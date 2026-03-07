/* ignore-breakpoints */
export default function OwnerStrategyPanel({
  insightOwnerId,
  insightOwnerLabel,
  isCurrentUserOwner,
  ownerStrategyInsights,
  recommendation,
}) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">
        Owner Strategy Panel ({insightOwnerLabel || `Owner ${insightOwnerId || '-'}`}
        {isCurrentUserOwner ? ' - You' : ''})
      </div>
      {!ownerStrategyInsights ? (
        <div className="mt-2 text-xs text-slate-500">
          Strategy guidance is unavailable until owner and budget context load.
        </div>
      ) : (
        <>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-300">
            <div title="Remaining budget compared to league mean.">
              <div className="text-slate-500">Budget vs League</div>
              <div className="font-semibold">
                ${Number(ownerStrategyInsights.ownerStats.budget || 0).toFixed(0)} / ${Number(
                  ownerStrategyInsights.leagueAvgBudget || 0
                ).toFixed(0)}
              </div>
            </div>
            <div title="Spend velocity versus league spend/slot pace.">
              <div className="text-slate-500">Aggressiveness</div>
              <div className="font-semibold">
                {ownerStrategyInsights.aggressivenessIndex >= 1.15
                  ? 'Aggressive'
                  : ownerStrategyInsights.aggressivenessIndex <= 0.9
                  ? 'Conservative'
                  : 'Balanced'}
              </div>
            </div>
            <div title="Composite signal of bid discipline + roster balance + budget safety.">
              <div className="text-slate-500">Strategy Alignment</div>
              <div className="font-semibold text-emerald-300">
                {ownerStrategyInsights.strategyAlignmentScore}
              </div>
            </div>
            <div title="Biggest roster gap versus league average by position.">
              <div className="text-slate-500">Positional Balance</div>
              <div className="font-semibold">
                {ownerStrategyInsights.mostBehindPosition
                  ? `${ownerStrategyInsights.mostBehindPosition.position} ${ownerStrategyInsights.mostBehindPosition.delta.toFixed(1)}`
                  : 'Even'}
              </div>
            </div>
          </div>

          <div className="mt-3 rounded border border-slate-800 p-2 text-xs text-slate-300">
            <div className="mb-1 text-slate-500">Budget Impact</div>
            {recommendation ? (
              <div>
                If you win at ${Number(recommendation.recommended_bid || 0).toFixed(2)}, you keep ${Math.max(
                  0,
                  Number(ownerStrategyInsights.ownerStats.budget || 0) -
                    Number(recommendation.recommended_bid || 0)
                ).toFixed(2)} left.
              </div>
            ) : (
              <div>No recommendation selected yet.</div>
            )}
          </div>

          {ownerStrategyInsights.exceedsPosCap ? (
            <div className="mt-2 rounded border border-rose-900 bg-rose-950/40 px-2 py-1 text-xs text-rose-300">
              Strategy alert: this bid exceeds your {ownerStrategyInsights.selectedPos} max spend plan (${Number(
                ownerStrategyInsights.posMaxSpend || 0
              ).toFixed(0)}).
            </div>
          ) : null}

          {ownerStrategyInsights.mostBehindPosition?.delta < -1 ? (
            <div className="mt-2 rounded border border-amber-900 bg-amber-950/40 px-2 py-1 text-xs text-amber-300">
              You are behind league average at {ownerStrategyInsights.mostBehindPosition.position}.
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
