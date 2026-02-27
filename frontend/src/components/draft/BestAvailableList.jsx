import React from 'react';

export default function BestAvailableList({ players = [] }) {
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg overflow-hidden flex flex-col h-full">
      <div className="bg-slate-800 p-2 border-b border-slate-700">
        <h2 className="text-cyan-400 font-bold text-sm uppercase tracking-wider">
          Best Available
        </h2>
      </div>
      <div className="overflow-y-auto max-h-[400px]">
        <table className="w-full text-left text-xs">
          <thead className="text-slate-500 uppercase bg-slate-900 sticky top-0">
            <tr>
              <th className="p-2">Rank</th>
              <th className="p-2">Player</th>
              <th className="p-2 text-right">Proj. $</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {players.map((p) => (
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
