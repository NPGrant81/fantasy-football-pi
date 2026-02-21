import React from 'react';

export default function WaiverTable({
  players = [],
  onClaim,
  processingId,
  loading = false,
}) {
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
            <th className="px-4 py-3">Player</th>
            <th className="px-4 py-3">Pos</th>
            <th className="px-4 py-3">Team</th>
            <th className="px-4 py-3">Projected</th>
            <th className="px-4 py-3 text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {players.map((player) => (
            <tr key={player.id} className="border-t border-slate-800 hover:bg-slate-800/30">
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
