import React from 'react';

export default function BestAvailableList({ players = [], open = true, onToggle }) {
  const [filterPos, setFilterPos] = React.useState('ALL');
  const [sortField, setSortField] = React.useState('rank');
  const [sortAsc, setSortAsc] = React.useState(true);

  // apply filtering
  const filtered = players.filter(
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
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-2">
        <button
          onClick={onToggle}
          className="text-sm text-yellow-400"
        >
          Show Best Available ▶
        </button>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg overflow-hidden flex flex-col h-full md:block">
      <div className="flex justify-between items-center bg-slate-800 p-2 border-b border-slate-700">
        <h2 className="text-cyan-400 font-bold text-sm uppercase tracking-wider">
          Best Available
        </h2>
        <button onClick={onToggle} className="text-xs text-yellow-400">
          ◀
        </button>
      </div>

      {/* position filters */}
      <div className="bg-slate-800 p-2 border-b border-slate-700 flex flex-wrap gap-1">
        {['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DEF'].map((pos) => (
          <button
            key={pos}
            onClick={() => setFilterPos(pos)}
            className={`text-[10px] font-bold px-2 py-1 rounded border transition uppercase ${
              filterPos === pos
                ? 'bg-yellow-500 text-black border-yellow-500'
                : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
            }`}
          >
            {pos}
          </button>
        ))}
      </div>

      <div className="overflow-y-auto max-h-[400px]">
        <table className="w-full text-left text-xs">
          <thead className="text-slate-500 uppercase bg-slate-900 sticky top-0">
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
          <tbody className="divide-y divide-slate-800">
            {sorted.map((p) => (
              <tr key={p.id} className="hover:bg-slate-800 transition-colors">
                <td className="p-2 text-slate-400">{p.rank}</td>
                <td className="p-2 font-semibold text-white">
                  <span className="text-cyan-500 mr-2">{p.pos}</span>
                  {p.name}
                </td>
                <td className="p-2 text-right text-green-400 font-mono">
                  ${p.projectedValue}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
