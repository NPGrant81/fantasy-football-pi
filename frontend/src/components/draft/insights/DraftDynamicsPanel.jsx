/* ignore-breakpoints */
export default function DraftDynamicsPanel({ draftDynamics }) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">
        Draft Dynamics Sidebar
      </div>

      <div className="mt-2 text-xs text-slate-300">
        <div className="text-slate-500" title="Recent realized price versus model value baseline.">
          Inflation / Deflation Trend
        </div>
        <div className="font-semibold">
          {Number(draftDynamics.inflationIndex || 1).toFixed(2)}x{' '}
          {draftDynamics.inflationIndex >= 1.1
            ? 'Inflating'
            : draftDynamics.inflationIndex <= 0.9
            ? 'Deflating'
            : 'Stable'}
        </div>
      </div>

      <div className="mt-3">
        <div className="mb-1 text-xs text-slate-500" title="Remaining owner budgets ranked high to low.">
          Remaining Budget Distribution
        </div>
        <div className="max-h-24 space-y-1 overflow-y-auto text-[11px]">
          {draftDynamics.budgetDistribution.slice(0, 8).map((row) => {
            const pct = Math.max(
              5,
              Math.min(
                100,
                Number(draftDynamics.leagueAvgBudget || 1) > 0
                  ? (Number(row.budget) / Number(draftDynamics.leagueAvgBudget || 1)) * 60
                  : 20
              )
            );
            return (
              <div key={row.owner_id}>
                <div className="flex items-center justify-between text-slate-300">
                  <span className="truncate pr-2">{row.owner_name}</span>
                  <span>${Number(row.budget).toFixed(0)}</span>
                </div>
                <div className="h-1.5 w-full rounded bg-slate-800">
                  <div className="h-1.5 rounded bg-cyan-500" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-3">
        <div className="mb-1 text-xs text-slate-500" title="Remaining roster demand versus available pool and replacement value.">
          Positional Demand / Scarcity Curve
        </div>
        <div className="space-y-1 text-[11px]">
          {draftDynamics.byPositionDemand.map((row) => (
            <div
              key={row.position}
              className="rounded border border-slate-800 px-2 py-1 text-slate-300"
            >
              <div className="flex items-center justify-between">
                <span>{row.position}</span>
                <span>{row.remainingSlots} need / {row.availableCount} avail</span>
              </div>
              <div className="mt-1 h-1.5 w-full rounded bg-slate-800">
                <div
                  className={`h-1.5 rounded ${
                    row.scarcity >= 80
                      ? 'bg-rose-500'
                      : row.scarcity >= 55
                      ? 'bg-amber-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(100, row.scarcity)}%` }}
                />
              </div>
              <div className="mt-1 text-slate-500">
                Replacement level: ${Number(row.replacementLevelValue || 0).toFixed(1)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
