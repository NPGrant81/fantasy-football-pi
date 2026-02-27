import React from 'react';

/**
 * currentBudget, openSlots, currentBid, onBid(newAmount)
 */
export default function AuctionInterface({
  currentBudget,
  openSlots,
  currentBid,
  onBid,
}) {
  const calculateMaxBid = (budget, slots) => {
    const reservedForOthers = slots - 1;
    const max = budget - reservedForOthers;
    return max > 0 ? max : 0;
  };
  const maxBid = calculateMaxBid(currentBudget, openSlots);
  const handleQuickBid = (inc) => {
    const newBid = currentBid + inc;
    if (newBid <= maxBid) onBid(newBid);
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="text-center bg-black/40 p-4 rounded border border-cyan-900/50">
        <span className="text-[10px] text-slate-500 uppercase block">
          Current Bid
        </span>
        <span className="text-4xl font-black text-green-400 font-mono">
          ${currentBid}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <button
          onClick={() => handleQuickBid(1)}
          disabled={currentBid + 1 > maxBid}
          className="bg-slate-700 hover:bg-cyan-600 disabled:opacity-30 py-2 rounded font-bold transition-all"
        >
          +$1
        </button>
        <button
          onClick={() => handleQuickBid(5)}
          disabled={currentBid + 5 > maxBid}
          className="bg-slate-700 hover:bg-cyan-600 disabled:opacity-30 py-2 rounded font-bold transition-all"
        >
          +$5
        </button>
        <button
          onClick={() => onBid(maxBid)}
          disabled={currentBid >= maxBid}
          className="bg-red-900 hover:bg-red-600 disabled:opacity-30 py-2 rounded font-bold transition-all"
        >
          MAX
        </button>
      </div>
      <div className="flex justify-between text-[10px] px-1 font-mono uppercase">
        <span className="text-slate-400">Budget: ${currentBudget}</span>
        <span className="text-red-400">Limit: ${maxBid}</span>
      </div>
    </div>
  );
}
