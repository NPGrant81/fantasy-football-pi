import React from 'react';

export default function BestAvailableList({
  players = [],
  open = true,
  onToggle,
}) {
  const [filterPos, setFilterPos] = React.useState('ALL');
  const [sortField, setSortField] = React.useState('rank');
  const [sortAsc, setSortAsc] = React.useState(true);

  const normalizedPlayers = React.useMemo(
    () =>
      players.map((player) => ({
        ...player,
        pos: player.pos || player.position || 'NA',
        projectedValue:
          player.projectedValue ??
          player.projected_value ??
          player.auction_value ??
          player.value ??
          0,
        rank: player.rank ?? player.adp ?? 9999,
      })),
    [players]
  );

  // apply filtering
  const filtered = normalizedPlayers.filter(
    (p) => filterPos === 'ALL' || p.pos === filterPos
  );

  // apply sorting
  const sorted = React.useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      let va = a[sortField];
      let vb = b[sortField];
      if (sortField === 'player') {
        va = a.name;
        vb = b.name;
      }
      if (sortField === 'proj') {
        va = a.projectedValue;
        vb = b.projectedValue;
      }
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
    return arr;
  }, [filtered, sortField, sortAsc]);

  const toggleSort = (field) => {
    if (sortField === field) {
      setSortAsc((v) => !v);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  if (!open) {
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-2 dark:bg-slate-900 dark:border-slate-700">
        <button onClick={onToggle} className="text-sm text-yellow-400">
          Show Best Available ▶
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden flex flex-col h-full md:block dark:bg-slate-900 dark:border-slate-700">
      <div className="flex justify-between items-center bg-slate-50 p-2 border-b border-slate-200 dark:bg-slate-800 dark:border-slate-700">
        <h2 className="text-cyan-700 font-bold text-sm uppercase tracking-wider dark:text-cyan-400">
          Best Available
        </h2>
        <button onClick={onToggle} className="text-xs text-yellow-400">
          ◀
        </button>
      </div>

      {/* position filters */}
      <div className="bg-slate-50 p-2 border-b border-slate-200 flex flex-wrap gap-1 dark:bg-slate-800 dark:border-slate-700">
        {['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DEF'].map((pos) => (
          <button
            key={pos}
            onClick={() => setFilterPos(pos)}
            className={`text-[10px] font-bold px-2 py-1 rounded border transition uppercase ${
              filterPos === pos
                ? 'bg-yellow-500 text-black border-yellow-500'
                : 'bg-white text-slate-600 border-slate-300 hover:text-slate-900 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700 dark:hover:text-white'
            }`}
          >
            {pos}
          </button>
        ))}
      </div>

      <div className="overflow-y-auto max-h-[400px]">
        <table className="w-full text-left text-xs">
          <thead className="text-slate-500 uppercase bg-slate-50 sticky top-0 dark:bg-slate-900">
            <tr>
              <th
                className="p-2 cursor-pointer"
                onClick={() => toggleSort('rank')}
              >
                Rank {sortField === 'rank' && (sortAsc ? '▲' : '▼')}
              </th>
              <th
                className="p-2 cursor-pointer"
                onClick={() => toggleSort('player')}
              >
                Player {sortField === 'player' && (sortAsc ? '▲' : '▼')}
              </th>
              <th
                className="p-2 text-right cursor-pointer"
                onClick={() => toggleSort('proj')}
              >
                Proj. $ {sortField === 'proj' && (sortAsc ? '▲' : '▼')}
              </th>
            </tr>
          </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {sorted.map((p) => (
              <tr key={p.id || `${p.name}-${p.pos}`} className="hover:bg-slate-100 transition-colors dark:hover:bg-slate-800">
                <td className="p-2 text-slate-400">{p.rank}</td>
                <td className="p-2 font-semibold text-slate-900 dark:text-white">
                  <span className="text-cyan-700 mr-2 dark:text-cyan-500">{p.pos}</span>
                  {p.name}
                  {p.injury_status && (
                    <span
                      title={p.injury_notes || p.injury_status}
                      className={`ml-1.5 inline-flex items-center rounded px-1 py-0 text-[9px] font-bold uppercase tracking-wide ${
                        p.injury_status === 'IR' || p.injury_status === 'OUT'
                          ? 'bg-red-600 text-white'
                          : p.injury_status === 'DOUBTFUL'
                          ? 'bg-orange-500 text-white'
                          : p.injury_status === 'QUESTIONABLE'
                          ? 'bg-yellow-400 text-black'
                          : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300'
                      }`}
                    >
                      {p.injury_status}
                    </span>
                  )}
                  {p.projected_return_date && (p.injury_status === 'IR' || p.injury_status === 'OUT') && (
                    <span className="ml-1 text-[9px] text-slate-400 dark:text-slate-500" title="Projected return">
                      &nbsp;↩{p.projected_return_date}
                    </span>
                  )}
                  {p.sentiment_label && p.sentiment_label !== 'neutral' && (
                    <span
                      title={`Sentiment: ${p.sentiment_label}${p.mention_count_7d ? ` (${p.mention_count_7d} mentions)` : ''}`}
                      className={`ml-1.5 inline-block h-2 w-2 rounded-full align-middle ${
                        p.sentiment_label === 'positive'
                          ? 'bg-green-500'
                          : 'bg-red-500'
                      }`}
                    />
                  )}
                </td>
                <td className="p-2 text-right text-green-700 font-mono dark:text-green-400">
                  ${p.projectedValue}
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={3} className="p-4 text-center text-slate-400">
                  No available players match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
