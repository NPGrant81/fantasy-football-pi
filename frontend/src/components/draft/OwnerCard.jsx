import { memo } from 'react';
import { normalizePos, POSITIONS } from '@utils';
import { getPosColor } from '../utils/uiHelpers';

const OwnerCard = memo(
  ({ owner, stats, isNominator, isSelectedWinner, myPicks, players }) => {
    // --- 1.1 STATUS & STYLING LOGIC ---
    const isBudgetLow = stats.budget < 10;
    const cardStatusClass = isSelectedWinner
      ? 'ring-2 ring-yellow-500 shadow-[0_0_20px_rgba(234,179,8,0.3)] scale-[1.02]'
      : isNominator
        ? 'border-blue-500 bg-slate-800/80'
        : 'border-slate-800 bg-slate-900/40';

    // --- 2.1 RENDER LOGIC (The View) ---
    return (
      <div
        className={`flex flex-col h-[400px] rounded-2xl border relative transition-all duration-300 ${cardStatusClass}`}
      >
        {/* 2.2 NOMINATION BADGE */}
        {isNominator && (
          <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-[10px] font-black px-4 py-1 rounded-full z-10 uppercase tracking-tighter shadow-lg">
            Nominating
          </div>
        )}

        {/* 2.3 HEADER SECTION */}
        <div
          className={`p-4 border-b flex justify-between items-start bg-black/20 rounded-t-2xl ${
            isNominator ? 'border-blue-500/30' : 'border-slate-800'
          }`}
        >
          <div className="w-2/3">
            <div
              className={`text-lg font-black truncate leading-tight uppercase tracking-tighter ${
                isNominator ? 'text-blue-300' : 'text-slate-100'
              }`}
            >
              {owner.username}
            </div>

            {/* Position Trackers */}
            <div className="flex flex-wrap gap-1 mt-2">
              {POSITIONS.map((pos) => {
                const count = stats.posCounts?.[pos] || 0;
                return (
                  <span
                    key={pos}
                    className={`text-[9px] font-bold px-1.5 py-0.5 rounded border transition-colors ${
                      count > 0
                        ? 'bg-slate-700 text-white border-slate-500'
                        : 'text-slate-600 border-transparent opacity-50'
                    }`}
                  >
                    {pos}:{count}
                  </span>
                );
              })}
            </div>
          </div>

          {/* Financials */}
          <div className="text-right w-1/3">
            <div
              className={`text-2xl font-mono font-black leading-none ${
                isBudgetLow ? 'text-red-500 animate-pulse' : 'text-green-400'
              }`}
            >
              ${stats.budget}
            </div>
            <div className="text-[10px] text-slate-500 uppercase font-bold mt-1">
              Max: ${stats.maxBid}
            </div>
          </div>
        </div>

        {/* 2.4 PICKS LIST (The Roster) */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar bg-slate-950/20">
          {myPicks.map((p) => {
            const playerDetails = players.find((pl) => pl.id === p.player_id);
            const pos = normalizePos(playerDetails?.position || 'UNK');
            return (
              <div
                key={p.id}
                className={`flex justify-between items-center p-2 rounded-lg border text-sm animate-in fade-in slide-in-from-bottom-1 ${getPosColor(pos)}`}
              >
                <div className="flex gap-2 items-center truncate">
                  <span className="font-black text-[9px] uppercase px-1.5 py-0.5 bg-black/20 rounded border border-white/10">
                    {pos}
                  </span>
                  <span className="truncate font-bold tracking-tight text-white/90">
                    {playerDetails?.name || p.player_name}
                  </span>
                </div>
                <span className="font-mono font-black text-xs">
                  ${p.amount}
                </span>
              </div>
            );
          })}

          {/* Empty Slot Placeholders */}
          {[...Array(stats.emptySpots)].map((_, i) => (
            <div
              key={`empty-${i}`}
              className="h-9 border border-dashed border-slate-800/60 rounded-lg bg-slate-900/10 flex items-center px-3"
            >
              <span className="text-[10px] font-black text-slate-800 uppercase tracking-widest">
                Open Slot
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }
);

export default OwnerCard;
