import React from 'react';

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
        className="inline-flex items-center gap-1 hover:text-white"
      >
        <span>{label}</span>
        <span className="text-[10px]">{sortIndicator(field)}</span>
      </button>
    </th>
  );

  if (loading) {
    return (
      <div className="p-20 text-center animate-pulse text-slate-500 font-black uppercase tracking-widest">
        Scanning the wire...
      </div>
    );
  }

  if (!players.length) {
    return (
      <div className="p-12 text-center text-slate-500 font-bold border border-slate-800 rounded-2xl bg-slate-900/40">
        No available players found.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border border-slate-800 rounded-2xl bg-slate-900/40">
      <table className="w-full text-left text-sm text-slate-300">
        <thead className="bg-slate-950/70 text-xs uppercase tracking-wider text-slate-500">
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
              className="border-t border-slate-800 hover:bg-slate-800/30"
            >
              <td className="px-4 py-3 font-bold text-white">{player.name}</td>
              <td className="px-4 py-3">{player.position}</td>
              <td className="px-4 py-3">{player.nfl_team || '-'}</td>
              <td className="px-4 py-3">{player.projected_points ?? 0}</td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={() => onClaim(player)}
                  disabled={processingId === player.id}
                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-bold uppercase text-white hover:bg-blue-500 disabled:opacity-60"
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
