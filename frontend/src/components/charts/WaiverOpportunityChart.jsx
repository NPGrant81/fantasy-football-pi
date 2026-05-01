import React, { useState, useEffect } from 'react';
import { useActiveLeague } from '@context/LeagueContext';
import { fetchWaiverOpportunitiesAnalytics } from '@api/analyticsApi';
import { LoadingState, ErrorState } from '@components/common/AsyncState';

const POSITIONS = ['All', 'QB', 'RB', 'WR', 'TE', 'K'];

const POSITION_COLORS = {
  QB: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300',
  RB: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  WR: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300',
  TE: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  K: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300',
};

/**
 * Given a 0–1 intensity value, return a Tailwind-compatible rgba background color string.
 * Heatmap cells go from white (0) to indigo (1).
 */
function heatmapColor(value, max) {
  if (max <= 0) return 'rgba(226,232,240,0.3)';
  const intensity = Math.min(value / max, 1);
  // Interpolate: low = slate-100, high = indigo-600
  const r = Math.round(238 - intensity * (238 - 79));
  const g = Math.round(242 - intensity * (242 - 70));
  const b = Math.round(248 - intensity * (248 - 229));
  const alpha = 0.2 + intensity * 0.8;
  return `rgba(${r},${g},${b},${alpha})`;
}

function TrendBadge({ trend }) {
  if (trend > 2) {
    return (
      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300 text-xs rounded font-medium">
        ↑ Hot
      </span>
    );
  }
  if (trend < -2) {
    return (
      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 text-xs rounded font-medium">
        ↓ Cold
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 text-xs rounded">
      → Stable
    </span>
  );
}

export default function WaiverOpportunityChart() {
  const leagueId = useActiveLeague();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [posFilter, setPosFilter] = useState('All');
  const [view, setView] = useState('heatmap'); // 'heatmap' | 'table'
  const [highlightBreakouts, setHighlightBreakouts] = useState(false);

  useEffect(() => {
    if (!leagueId) return;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const position = posFilter !== 'All' ? posFilter : null;
        const response = await fetchWaiverOpportunitiesAnalytics(leagueId, undefined, position);
        setData(response.data);
      } catch (err) {
        setError(err?.message || 'Failed to load waiver wire data');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [leagueId, posFilter]);

  if (loading) return <LoadingState message="Scanning waiver wire opportunities..." className="h-96" />;
  if (error) return <ErrorState message={error} />;
  if (!data?.rows?.length) {
    return (
      <div className="text-center p-8 text-slate-600 dark:text-slate-400">
        <p>No waiver wire opportunity data available for this season.</p>
        <p className="text-sm mt-1">Player weekly stats may not yet be loaded.</p>
      </div>
    );
  }

  const rows = highlightBreakouts ? data.rows.filter((r) => r.breakout_flag) : data.rows;
  const allWeeks = data.all_weeks || [];
  const heatmapMax = data.heatmap_max || 30;

  return (
    <div className="w-full bg-white dark:bg-slate-900/30 rounded-lg border border-slate-200 dark:border-slate-700 p-4 space-y-4">
      {/* Header / Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Waiver Wire Opportunity Tracker
          </h2>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Free agents ranked by rolling opportunity volume. 
            <span className="font-medium text-emerald-600 dark:text-emerald-400"> ↑ Hot</span> = trending up over last 4 weeks.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Position filter */}
          <div className="flex rounded overflow-hidden border border-slate-200 dark:border-slate-700 text-xs">
            {POSITIONS.map((pos) => (
              <button
                key={pos}
                onClick={() => setPosFilter(pos)}
                className={`px-2 py-1 transition-colors ${
                  posFilter === pos
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                {pos}
              </button>
            ))}
          </div>

          {/* View toggle */}
          <div className="flex rounded overflow-hidden border border-slate-200 dark:border-slate-700 text-xs">
            {['heatmap', 'table'].map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-3 py-1 capitalize transition-colors ${
                  view === v
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                {v}
              </button>
            ))}
          </div>

          {/* Breakouts only */}
          <button
            onClick={() => setHighlightBreakouts((p) => !p)}
            className={`text-xs px-3 py-1 rounded border transition-colors ${
              highlightBreakouts
                ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400'
                : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300'
            }`}
          >
            🔥 Breakouts only
          </button>
        </div>
      </div>

      {/* No breakouts message */}
      {highlightBreakouts && rows.length === 0 && (
        <div className="p-4 text-center text-slate-600 dark:text-slate-400 text-sm">
          No breakout candidates detected this season. Try clearing the filter.
        </div>
      )}

      {/* Heatmap View */}
      {view === 'heatmap' && rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>
                <th className="text-left p-2 text-slate-700 dark:text-slate-300 font-semibold bg-slate-50 dark:bg-slate-800 sticky left-0 z-10 min-w-[160px]">
                  Player
                </th>
                <th className="p-2 text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800 whitespace-nowrap">
                  Opp Score
                </th>
                <th className="p-2 text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800 whitespace-nowrap">
                  Trend
                </th>
                {allWeeks.map((w) => (
                  <th
                    key={w}
                    className="p-2 text-center text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800 min-w-[40px]"
                  >
                    Wk{w}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((player) => (
                <tr
                  key={player.player_id}
                  className={`border-t border-slate-100 dark:border-slate-800 ${
                    player.breakout_flag ? 'bg-emerald-50/40 dark:bg-emerald-900/10' : ''
                  }`}
                >
                  {/* Player name + position */}
                  <td className="p-2 sticky left-0 bg-white dark:bg-slate-900 z-10">
                    <div className="flex items-center gap-1">
                      {player.breakout_flag && (
                        <span title="Breakout candidate" className="text-emerald-500">🔥</span>
                      )}
                      <div>
                        <p className="font-medium text-slate-900 dark:text-slate-100 truncate max-w-[130px]">
                          {player.player_name}
                        </p>
                        <div className="flex items-center gap-1 mt-0.5">
                          <span
                            className={`px-1 py-0.5 rounded text-[10px] font-medium ${
                              POSITION_COLORS[player.position] || POSITION_COLORS.K
                            }`}
                          >
                            {player.position}
                          </span>
                          <span className="text-slate-500 dark:text-slate-400 text-[10px]">
                            {player.nfl_team}
                          </span>
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Opportunity score */}
                  <td className="p-2 text-center font-semibold text-slate-900 dark:text-slate-100">
                    {player.opportunity_score.toFixed(1)}
                  </td>

                  {/* Trend badge */}
                  <td className="p-2 text-center">
                    <TrendBadge trend={player.trend} />
                  </td>

                  {/* Week cells (heatmap) */}
                  {allWeeks.map((w) => {
                    const fp = player.weekly_scores[String(w)];
                    const bgColor = fp != null ? heatmapColor(fp, heatmapMax) : 'transparent';
                    return (
                      <td
                        key={w}
                        title={fp != null ? `Week ${w}: ${fp} pts` : `Week ${w}: —`}
                        className="p-0 text-center border border-slate-100 dark:border-slate-800"
                        style={{ backgroundColor: bgColor }}
                      >
                        <span className="block py-2 text-[11px] font-medium text-slate-800 dark:text-slate-200">
                          {fp != null ? fp.toFixed(1) : '—'}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Table View */}
      {view === 'table' && rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                <th className="text-left p-2">Player</th>
                <th className="p-2 text-center">Pos</th>
                <th className="p-2 text-center">Team</th>
                <th className="p-2 text-center">Season Avg</th>
                <th className="p-2 text-center">L3 Avg</th>
                <th className="p-2 text-center">Targets</th>
                <th className="p-2 text-center">Carries</th>
                <th className="p-2 text-center">RZ Tgts</th>
                <th className="p-2 text-center">Opp Score</th>
                <th className="p-2 text-center">Trend</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((player, idx) => (
                <tr
                  key={player.player_id}
                  className={`border-t border-slate-100 dark:border-slate-800 ${
                    idx % 2 === 0 ? '' : 'bg-slate-50/40 dark:bg-slate-800/20'
                  } ${player.breakout_flag ? 'bg-emerald-50/60 dark:bg-emerald-900/10' : ''}`}
                >
                  <td className="p-2">
                    <div className="flex items-center gap-1">
                      {player.breakout_flag && <span title="Breakout">🔥</span>}
                      <span className="font-medium text-slate-900 dark:text-slate-100">
                        {player.player_name}
                      </span>
                    </div>
                  </td>
                  <td className="p-2 text-center">
                    <span
                      className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                        POSITION_COLORS[player.position] || POSITION_COLORS.K
                      }`}
                    >
                      {player.position}
                    </span>
                  </td>
                  <td className="p-2 text-center text-slate-600 dark:text-slate-400 text-xs">
                    {player.nfl_team}
                  </td>
                  <td className="p-2 text-center text-slate-900 dark:text-slate-100">
                    {player.season_avg.toFixed(1)}
                  </td>
                  <td className="p-2 text-center">
                    <span
                      className={`font-semibold ${
                        player.recent_avg > player.season_avg
                          ? 'text-emerald-700 dark:text-emerald-400'
                          : player.recent_avg < player.season_avg
                          ? 'text-red-600 dark:text-red-400'
                          : 'text-slate-700 dark:text-slate-300'
                      }`}
                    >
                      {player.recent_avg.toFixed(1)}
                    </span>
                  </td>
                  <td className="p-2 text-center text-slate-700 dark:text-slate-300">
                    {player.total_targets || '—'}
                  </td>
                  <td className="p-2 text-center text-slate-700 dark:text-slate-300">
                    {player.total_carries || '—'}
                  </td>
                  <td className="p-2 text-center text-slate-700 dark:text-slate-300">
                    {player.total_rz_targets || '—'}
                  </td>
                  <td className="p-2 text-center font-bold text-indigo-600 dark:text-indigo-400">
                    {player.opportunity_score.toFixed(1)}
                  </td>
                  <td className="p-2 text-center">
                    <TrendBadge trend={player.trend} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      <div className="border-t border-slate-200 dark:border-slate-700 pt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-slate-700 dark:text-slate-300">
        <div>
          <p className="font-semibold mb-1">Opportunity Score</p>
          <p>Composite metric: avg fantasy points + (targets/game × 0.5) + (carries/game × 0.3) + (red-zone targets/game × 0.8)</p>
        </div>
        <div>
          <p className="font-semibold mb-1">Heatmap Colors</p>
          <div className="flex items-center gap-2">
            <div className="flex gap-0.5">
              {[0.1, 0.3, 0.5, 0.7, 0.9].map((v) => (
                <div
                  key={v}
                  className="w-6 h-4 rounded-sm"
                  style={{ backgroundColor: heatmapColor(v * 30, 30) }}
                />
              ))}
            </div>
            <span>Low → High</span>
          </div>
        </div>
      </div>
    </div>
  );
}
