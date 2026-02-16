import React from 'react';
import { getPosColor, normalizePos } from '@utils';

export default function DraftHistoryFeed({ history, owners }) {
  // We reverse the history so the most recent pick is at the top
  const recentPicks = [...history].reverse();

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl flex flex-col h-full overflow-hidden shadow-2xl">
      <div className="p-4 border-b border-slate-800 bg-slate-900/50">
        <h2 className="text-yellow-500 font-black uppercase italic tracking-tighter flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </span>
          Live Draft Feed
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
        {recentPicks.length > 0 ? (
          recentPicks.map((pick) => {
            const owner = owners.find(o => o.id === pick.owner_id);
            return (
              <div 
                key={pick.id || `${pick.player_id}-${pick.timestamp}`} 
                className="bg-slate-950 p-3 rounded-xl border border-slate-800 animate-in slide-in-from-right duration-500"
              >
                <div className="flex justify-between items-start mb-1">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">
                    {owner?.username || "Unknown Owner"}
                  </span>
                  <span className="text-[10px] font-mono text-slate-600">
                    {new Date(pick.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
                
                <div className="text-white font-bold text-sm truncate uppercase tracking-tight">
                  {pick.player_name}
                </div>

                <div className="flex justify-between items-center mt-2">
                  <span className={`text-[9px] font-black px-1.5 py-0.5 rounded shadow-sm ${getPosColor(pick.position)}`}>
                    {normalizePos(pick.position)}
                  </span>
                  <span className="text-green-400 font-mono font-bold text-sm">
                    ${pick.amount}
                  </span>
                </div>
              </div>
            );
          })
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 italic text-sm text-center px-4 py-20">
            <div className="mb-4 text-3xl opacity-20">🔨</div>
            The auction hasn't started yet.
          </div>
        )}
      </div>
    </div>
  );
}