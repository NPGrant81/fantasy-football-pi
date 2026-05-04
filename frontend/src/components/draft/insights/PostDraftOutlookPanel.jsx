import { EmptyState } from '@components/common/AsyncState';

function metricTone(value, positiveGood = true) {
  if (value == null || Number.isNaN(Number(value))) return 'text-slate-600 dark:text-slate-300';
  const n = Number(value);
  if (n === 0) return 'text-slate-600 dark:text-slate-300';
  if (positiveGood) {
    return n > 0
      ? 'text-emerald-700 dark:text-emerald-300'
      : 'text-rose-700 dark:text-rose-300';
  }
  return n > 0
    ? 'text-rose-700 dark:text-rose-300'
    : 'text-emerald-700 dark:text-emerald-300';
}

export default function PostDraftOutlookPanel({ outlook, ownerLabel }) {
  if (!outlook) {
    return (
      <div className="rounded-md border border-slate-300 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950/60">
        <EmptyState
          message="Post-draft outlook appears once draft and owner context are available."
          className="text-xs"
        />
      </div>
    );
  }

  const {
    rosterStrengthScore,
    projectedStarterValue,
    budgetDeltaVsLeague,
    strongestPositions,
    thinnestPositions,
    highRiskPlayers,
    simulationDelta,
    positionCounts,
  } = outlook;

  return (
    <div className="rounded-md border border-slate-300 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950/60">
      <div className="mb-2 text-[11px] uppercase tracking-wide text-slate-400">
        Post-Draft Outlook ({ownerLabel || 'Selected Owner'})
      </div>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900/60">
          <div className="text-[10px] uppercase text-slate-500">Roster Strength</div>
          <div className="text-lg font-black text-indigo-700 dark:text-indigo-300">
            {Number(rosterStrengthScore || 0).toFixed(1)}
          </div>
        </div>
        <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900/60">
          <div className="text-[10px] uppercase text-slate-500">Starter Value</div>
          <div className="text-lg font-black text-cyan-700 dark:text-cyan-300">
            ${Number(projectedStarterValue || 0).toFixed(0)}
          </div>
        </div>
        <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900/60">
          <div className="text-[10px] uppercase text-slate-500">Budget vs League</div>
          <div className={`text-lg font-black ${metricTone(budgetDeltaVsLeague, false)}`}>
            {Number(budgetDeltaVsLeague || 0) >= 0 ? '+' : ''}
            {Number(budgetDeltaVsLeague || 0).toFixed(0)}
          </div>
        </div>
        <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900/60">
          <div className="text-[10px] uppercase text-slate-500">Sim Delta</div>
          <div className={`text-lg font-black ${metricTone(simulationDelta, true)}`}>
            {simulationDelta == null
              ? '—'
              : `${Number(simulationDelta) >= 0 ? '+' : ''}${Number(simulationDelta).toFixed(1)} pts`}
          </div>
        </div>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-3">
        <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900/60">
          <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
            Strongest Positions
          </div>
          {strongestPositions.length ? (
            <ul className="space-y-0.5 text-xs text-slate-700 dark:text-slate-300">
              {strongestPositions.map((item) => (
                <li key={item.position}>
                  {item.position}: {item.count}/{item.cap}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-500">No clear strengths yet.</p>
          )}
        </div>

        <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900/60">
          <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-amber-700 dark:text-amber-300">
            Thinnest Positions
          </div>
          {thinnestPositions.length ? (
            <ul className="space-y-0.5 text-xs text-slate-700 dark:text-slate-300">
              {thinnestPositions.map((item) => (
                <li key={item.position}>
                  {item.position}: {item.count}/{item.cap}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-500">Depth looks balanced.</p>
          )}
        </div>

        <div className="rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900/60">
          <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-rose-700 dark:text-rose-300">
            High-Risk Players
          </div>
          {highRiskPlayers.length ? (
            <ul className="space-y-0.5 text-xs text-slate-700 dark:text-slate-300">
              {highRiskPlayers.map((item) => (
                <li key={`${item.player_id}-${item.name}`}>
                  {item.name} ({item.position}) · risk {Number(item.risk).toFixed(0)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-500">No high-risk flags from current model inputs.</p>
          )}
        </div>
      </div>

      <div className="mt-3 rounded border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900/60">
        <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-500">
          Position Counts
        </div>
        <div className="flex flex-wrap gap-1.5">
          {positionCounts.map((item) => (
            <span
              key={item.position}
              className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700 dark:bg-slate-800 dark:text-slate-300"
            >
              {item.position} {item.count}/{item.cap}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
