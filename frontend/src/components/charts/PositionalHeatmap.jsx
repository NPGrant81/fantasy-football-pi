import React from 'react';
import { useActiveLeague } from '@context/LeagueContext';
import { fetchPositionalHeatmapAnalytics } from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import { EmptyState, ErrorState, LoadingState } from '@components/common/AsyncState';

const PROFILE_OPTIONS = [
  { value: 'standard', label: 'Standard' },
  { value: 'pass-catching-rbs', label: 'Pass-catching RBs' },
];

const POSITION_OPTIONS = ['QB', 'RB', 'WR', 'TE'];

function cellColor(value, minValue, maxValue) {
  if (maxValue <= minValue) {
    return 'rgba(148, 163, 184, 0.25)';
  }
  const normalized = (value - minValue) / (maxValue - minValue);
  const intensity = Math.max(0, Math.min(1, normalized));
  const alpha = 0.2 + intensity * 0.75;
  const r = Math.round(226 + intensity * 20);
  const g = Math.round(232 - intensity * 128);
  const b = Math.round(240 - intensity * 165);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export default function PositionalHeatmap() {
  const leagueId = useActiveLeague();
  const [profile, setProfile] = React.useState('standard');
  const [streamPosition, setStreamPosition] = React.useState('WR');
  const [isMockData, setIsMockData] = React.useState(false);
  const [fallbackReason, setFallbackReason] = React.useState('');
  const [rows, setRows] = React.useState([]);
  const [positions, setPositions] = React.useState(POSITION_OPTIONS);
  const [streamingSuggestions, setStreamingSuggestions] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    if (!leagueId) {
      setError('League not found.');
      setLoading(false);
      return;
    }

    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const season = new Date().getFullYear();
        const payload = (await fetchPositionalHeatmapAnalytics(leagueId, season, profile, streamPosition)) || {};
        if (!mounted) return;
        setIsMockData(Boolean(payload.mock_data));
        setFallbackReason(String(payload.fallback_reason || ''));
        setRows(Array.isArray(payload.rows) ? payload.rows : []);
        setPositions(Array.isArray(payload.positions) && payload.positions.length ? payload.positions : POSITION_OPTIONS);
        setStreamingSuggestions(Array.isArray(payload.streaming_suggestions) ? payload.streaming_suggestions : []);
      } catch (err) {
        if (!mounted) return;
        setError(normalizeApiError(err, 'Failed to load positional heatmap data.'));
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      mounted = false;
    };
  }, [leagueId, profile, streamPosition]);

  if (loading) {
    return <LoadingState message="Loading positional matchup heatmap..." className="h-72" />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!rows.length || !positions.length) {
    return <EmptyState message="No positional heatmap data available." />;
  }

  const allValues = rows.flatMap((row) => positions.map((pos) => Number(row?.values?.[pos] || 0)));
  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">Positional Matchup Heatmap</h3>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            Team-by-position defensive weakness grid for lineup and waiver decisions.
          </p>
          {isMockData ? (
            <span className="mt-1 inline-flex rounded bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
              Fallback mode: Mock data{fallbackReason ? ` (${fallbackReason})` : ''}
            </span>
          ) : (
            <span className="mt-1 inline-flex rounded bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
              Live mode: Aggregated weekly matchup data
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Heatmap profile"
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-800 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
            value={profile}
            onChange={(event) => setProfile(event.target.value)}
          >
            {PROFILE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>

          <select
            aria-label="Streaming focus"
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-800 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
            value={streamPosition}
            onChange={(event) => setStreamPosition(event.target.value)}
          >
            {POSITION_OPTIONS.map((pos) => (
              <option key={pos} value={pos}>{`Streaming focus: ${pos}`}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
        <table className="w-full text-xs sm:text-sm">
          <thead>
            <tr className="bg-slate-50 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
              <th className="p-2 text-left">Defense</th>
              {positions.map((pos) => (
                <th key={pos} className="p-2 text-center">{pos}</th>
              ))}
              <th className="p-2 text-left">Weakest vs</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr
                key={row.defense_team}
                className={index % 2 === 0 ? 'bg-white dark:bg-slate-900/20' : 'bg-slate-50/40 dark:bg-slate-800/20'}
              >
                <td className="p-2 font-semibold text-slate-900 dark:text-slate-100">{row.defense_team}</td>
                {positions.map((pos) => {
                  const value = Number(row?.values?.[pos] || 0);
                  return (
                    <td
                      key={`${row.defense_team}-${pos}`}
                      className="p-2 text-center font-medium text-slate-900 dark:text-slate-100"
                      style={{ backgroundColor: cellColor(value, minValue, maxValue) }}
                      title={`${row.defense_team} vs ${pos}: ${value.toFixed(2)} points allowed`}
                    >
                      {value.toFixed(1)}
                    </td>
                  );
                })}
                <td className="p-2 text-slate-700 dark:text-slate-300">{row.weakest_position}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-3 dark:border-slate-700 dark:bg-slate-800/20">
        <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Weekly Streaming Suggestions</h4>
        <p className="mb-2 text-xs text-slate-600 dark:text-slate-400">
          Prioritize players at {streamPosition} facing defenses with the highest points allowed.
        </p>
        <ul className="space-y-1 text-xs text-slate-700 dark:text-slate-300">
          {streamingSuggestions.map((suggestion) => (
            <li key={`${suggestion.defense_team}-${suggestion.rank}`}>
              <span className="font-semibold">#{suggestion.rank} {suggestion.defense_team}</span>
              {` — ${suggestion.points_allowed.toFixed(1)} points allowed (${suggestion.target_position})`}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
