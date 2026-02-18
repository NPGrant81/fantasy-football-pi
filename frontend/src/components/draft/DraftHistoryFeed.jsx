import { normalizePos } from '@utils';
import { getPosColor } from '../../utils/uiHelpers';

export default function DraftHistoryFeed({ history = [], owners = [] }) {
  // --- 1.1 DATA TRANSFORMATION ---
  // Sort by timestamp ascending for ticker order
  const recentPicks = [...history].sort(
    (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
  );

  // --- 2.1 RENDER LOGIC (Horizontal Ticker) ---
  return (
    <div className="fixed bottom-0 left-0 w-full bg-slate-950 border-t border-yellow-600 z-50 shadow-2xl overflow-x-hidden">
      <div className="flex items-center gap-4 py-2 animate-marquee whitespace-nowrap">
        <span className="text-yellow-500 font-black uppercase italic tracking-tighter flex items-center gap-2 ml-4">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </span>
          Live Draft Feed:
        </span>
        {recentPicks.length > 0 ? (
          recentPicks.map((pick) => {
            const owner = owners.find((o) => o.id === pick.owner_id);
            return (
              <span
                key={pick.id || `${pick.player_id}-${pick.timestamp}`}
                className="inline-flex items-center bg-slate-900 border border-slate-800 rounded-full px-4 py-1 mx-1 text-xs font-bold text-white shadow hover:border-yellow-400 transition-colors"
              >
                <span className="text-yellow-400 mr-2">{owner?.username || 'Ghost Owner'}</span>
                <span className="uppercase font-black tracking-tight mr-2">{pick.player_name}</span>
                <span className={`text-[9px] font-black px-2 py-0.5 rounded border mr-2 ${getPosColor(pick.position)}`}>{normalizePos(pick.position)}</span>
                <span className="text-green-400 font-mono font-black text-xs mr-2">${pick.amount}</span>
                <span className="text-slate-500 font-mono">{new Date(pick.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
              </span>
            );
          })
        ) : (
          <span className="text-slate-600 italic text-sm px-4">Waiting for the first nomination...</span>
        )}
      </div>
      {/* Marquee animation CSS */}
      <style>{`
        @keyframes marquee {
          0% { transform: translateX(100%); }
          100% { transform: translateX(-100%); }
        }
        .animate-marquee {
          animation: marquee 60s linear infinite;
        }
      `}</style>
    </div>
  );
}
