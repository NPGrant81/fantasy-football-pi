import React from 'react';
import { EmptyState, LoadingState } from '@components/common/AsyncState';
import { buttonPrimary, tableHead, tableSurface } from '@utils/uiStandards';

/* ignore-breakpoints */

export default function WaiverTable({
  players = [],
  onClaim,
  processingId,
  loading = false,
}) {
  const [sortField, setSortField] = React.useState('name');
  const [sortDirection, setSortDirection] = React.useState('asc');

  const toggleSort = (field) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }

    setSortField(field);
    setSortDirection('asc');
  };

  const sortedPlayers = React.useMemo(() => {
    const list = [...players];
    const directionFactor = sortDirection === 'asc' ? 1 : -1;

    list.sort((left, right) => {
      if (sortField === 'projected_points') {
        const a = Number(left.projected_points ?? 0);
        const b = Number(right.projected_points ?? 0);
        return (a - b) * directionFactor;
      }

      const a = String(left[sortField] ?? '').toLowerCase();
      const b = String(right[sortField] ?? '').toLowerCase();
      return a.localeCompare(b) * directionFactor;
    });

    return list;
  }, [players, sortField, sortDirection]);

  const sortIndicator = (field) => {
    if (sortField !== field) return '↕';
    return sortDirection === 'asc' ? '↑' : '↓';
  };

  const renderSortHeader = (field, label, align = 'left') => (
    <th className={`px-4 py-3 ${align === 'right' ? 'text-right' : ''}`}>
      <button
        type="button"
        onClick={() => toggleSort(field)}
        className="inline-flex items-center gap-1 text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
      >
        <span>{label}</span>
        <span className="text-[10px]">{sortIndicator(field)}</span>
      </button>
    </th>
  );

  if (loading) {
    return (
      <div className="rounded-xl border border-slate-300 bg-white/80 p-20 text-center font-black uppercase tracking-widest text-slate-500 animate-pulse dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
        <LoadingState message="Scanning the wire..." className="justify-center" />
      </div>
    );
  }

  if (!players.length) {
    return (
      <div className="rounded-xl border border-slate-300 bg-white/80 p-12 text-center font-bold text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
        <EmptyState message="No available players found." className="justify-center" />
      </div>
    );
  }

  return (
    <div className={tableSurface}>
      <table className="w-full text-left text-sm text-slate-700 dark:text-slate-300">
        <thead className={tableHead}>
          <tr>
            {renderSortHeader('name', 'Player')}
            {renderSortHeader('position', 'Pos')}
            {renderSortHeader('nfl_team', 'Team')}
            {renderSortHeader('projected_points', 'Projected')}
            <th className="px-4 py-3 text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {sortedPlayers.map((player) => (
            <tr
              key={player.id}
              className="border-t border-slate-300 hover:bg-slate-100 dark:border-slate-800 dark:hover:bg-slate-800/30"
            >
              <td className="px-4 py-3 font-bold text-slate-900 dark:text-white">
                {player.name}
              </td>
              <td className="px-4 py-3">{player.position}</td>
              <td className="px-4 py-3">{player.nfl_team || '-'}</td>
              <td className="px-4 py-3">{player.projected_points ?? 0}</td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={() => onClaim(player)}
                  disabled={processingId === player.id}
                  className={`${buttonPrimary} px-3 py-1.5 text-xs uppercase ${
                    processingId === player.id ? 'opacity-60' : ''
                  }`}
                >
                  {processingId === player.id ? 'Claiming...' : 'Claim'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
