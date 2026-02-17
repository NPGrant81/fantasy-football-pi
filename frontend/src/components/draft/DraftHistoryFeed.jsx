import { getPosColor, normalizePos } from '@utils';

export default function DraftHistoryFeed({ history = [], owners = [] }) {
  // --- 1.1 DATA TRANSFORMATION ---
  // Reverse history so the newest "Sold!" player is always at the top
  const recentPicks = [...history].sort(
    (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
  );

  // --- 2.1 RENDER LOGIC (The View) ---
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl flex flex-col h-full overflow-hidden shadow-2xl">
      {/* 2.2 FEED HEADER */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/50">
        <h2 className="text-yellow-500 font-black uppercase italic tracking-tighter flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </span>
          Live Draft Feed
        </h2>
      </div>

      {/* 2.3 SCROLLABLE ACTIVITY LIST */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar bg-slate-900/20">
        {recentPicks.length > 0 ? (
          recentPicks.map((pick) => {
            const owner = owners.find((o) => o.id === pick.owner_id);

            return (
              <div
                key={pick.id || `${pick.player_id}-${pick.timestamp}`}
                className="bg-slate-950 p-3 rounded-xl border border-slate-800 animate-in slide-in-from-right duration-500 hover:border-slate-600 transition-colors group"
              >
                {/* OWNER & TIMESTAMP */}
                <div className="flex justify-between items-start mb-1.5">
                  <span className="text-[10px] text-yellow-500/70 font-black uppercase tracking-widest group-hover:text-yellow-500 transition-colors">
                    {owner?.username || 'Ghost Owner'}
                  </span>
                  <span className="text-[9px] font-mono text-slate-600">
                    {new Date(pick.timestamp).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </span>
                </div>

                {/* PLAYER NAME */}
                <div className="text-white font-black text-sm truncate uppercase tracking-tight mb-2">
                  {pick.player_name}
                </div>

                {/* POSITION & PRICE */}
                <div className="flex justify-between items-center border-t border-slate-900 pt-2">
                  <span
                    className={`text-[9px] font-black px-2 py-0.5 rounded border ${getPosColor(pick.position)}`}
                  >
                    {normalizePos(pick.position)}
                  </span>
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] text-slate-500 font-bold uppercase">
                      Paid
                    </span>
                    <span className="text-green-400 font-mono font-black text-sm">
                      ${pick.amount}
                    </span>
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          /* 2.4 EMPTY STATE */
          <div className="h-full flex flex-col items-center justify-center text-slate-600 italic text-sm text-center px-4 py-20">
            <div className="mb-4 text-4xl opacity-10 grayscale">🔨</div>
            <p className="uppercase font-black tracking-widest text-xs opacity-40">
              Waiting for the first nomination...
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
