// frontend/src/components/OwnerCard.jsx
import React, { memo } from 'react';
import { normalizePos, getPosColor, POSITIONS } from '../utils/draftHelpers';

const OwnerCard = memo(({ 
  owner, 
  stats, 
  isNominator, 
  isSelectedWinner, 
  myPicks, 
  players 
}) => {
  return (
    <div className={`flex flex-col h-96 rounded-lg border relative transition-all ${
      isSelectedWinner ? 'ring-2 ring-yellow-500 shadow-xl' : ''
    } ${
      isNominator ? 'border-blue-500 bg-slate-800' : 'border-slate-800 bg-slate-900/50'
    }`}>
      
      {isNominator && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-[10px] font-bold px-3 py-1 rounded-full z-10 uppercase">
          Nominating
        </div>
      )}

      {/* CARD HEADER */}
      <div className={`p-3 border-b flex justify-between items-end bg-black/20 rounded-t-lg ${
        isNominator ? 'border-blue-500/30' : 'border-slate-700'
      }`}>
        <div className="w-2/3">
          <div className={`font-bold truncate ${isNominator ? 'text-blue-300' : 'text-slate-200'}`}>
            {owner.username}
          </div>
          <div className="flex flex-wrap gap-1 mt-1">
            {POSITIONS.map(pos => (
              <span key={pos} className={`text-[9px] px-1 rounded ${
                stats.posCounts[pos] > 0 ? 'bg-slate-700 text-white border border-slate-600' : 'text-slate-600'
              }`}>
                {pos}:{stats.posCounts[pos]}
              </span>
            ))}
          </div>
        </div>
        <div className="text-right w-1/3">
          <div className={`text-2xl font-mono font-bold leading-none ${
            stats.remaining < 10 ? "text-red-400" : "text-green-400"
          }`}>
            ${stats.remaining}
          </div>
          <div className="text-[9px] text-slate-500 uppercase">Max: ${stats.maxBid}</div>
        </div>
      </div>

      {/* PICKS LIST */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
        {myPicks.map(p => {
          const playerDetails = players.find(pl => pl.id === p.player_id);
          const pos = normalizePos(playerDetails?.position || 'UNK');
          return (
            <div key={p.id} className={`flex justify-between items-center p-1.5 rounded border text-sm ${getPosColor(pos)}`}>
              <div className="flex gap-2 items-center truncate">
                <span className="font-bold text-[10px] opacity-70">{pos}</span>
                <span className="truncate">{playerDetails?.name}</span>
              </div>
              <span className="font-mono font-bold opacity-80">${p.amount}</span>
            </div>
          );
        })}
        {[...Array(stats.emptySpots)].map((_, i) => (
          <div key={i} className="h-6 border border-dashed border-slate-800 rounded bg-slate-900/10"></div>
        ))}
      </div>
    </div>
  );
});

export default OwnerCard;