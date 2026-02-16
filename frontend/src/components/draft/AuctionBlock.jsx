// frontend/src/components/AuctionBlock.jsx
import React from 'react';
import { POSITIONS, getPosColor, normalizePos } from '../utils/draftHelpers';

export default function AuctionBlock({
  playerName,
  handleSearchChange,
  suggestions,
  showSuggestions,
  selectSuggestion,
  posFilter,
  setPosFilter,
  winnerId,
  setWinnerId,
  owners,
  activeStats,
  bidAmount,
  setBidAmount,
  handleDraft,
  timeLeft,
  isTimerRunning,
  reset,
  start
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
      {/* PLAYER SEARCH & POSITION FILTERS */}
      <div className="md:col-span-5 relative">
        <div className="flex gap-1 mb-2 overflow-x-auto">
          {['ALL', ...POSITIONS].map(pos => (
            <button
              key={pos}
              onClick={() => setPosFilter(pos)}
              className={`text-[10px] font-bold px-2 py-1 rounded border transition ${
                posFilter === pos ? 'bg-yellow-500 text-black' : 'bg-slate-800 text-slate-400'
              }`}
            >
              {pos}
            </button>
          ))}
        </div>
        <input
          className="w-full p-3 rounded bg-slate-800 border border-slate-600 text-lg font-bold outline-none focus:border-yellow-500"
          value={playerName}
          onChange={handleSearchChange}
          placeholder="Search Player..."
        />
        {showSuggestions && suggestions.length > 0 && (
          <ul className="absolute z-50 w-full bg-slate-800 border border-slate-600 mt-1 rounded shadow-xl max-h-60 overflow-y-auto">
            {suggestions.map(p => (
              <li key={p.id} onClick={() => selectSuggestion(p)} className="p-2 hover:bg-slate-700 cursor-pointer flex justify-between border-b border-slate-700 text-sm">
                <span className="font-bold">{p.name}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${getPosColor(p.position)}`}>
                  {normalizePos(p.position)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* BIDDING CONTROLS */}
      <div className="md:col-span-4 bg-slate-800/50 p-2 rounded border border-slate-700">
        <label className="block text-slate-500 text-[10px] uppercase font-bold mb-1">Winning Bidder</label>
        <select
          className="w-full bg-slate-800 text-white border border-slate-600 rounded p-1.5 text-sm font-bold mb-2"
          value={winnerId || ""}
          onChange={(e) => setWinnerId(parseInt(e.target.value))}
        >
          {owners.map(o => <option key={o.id} value={o.id}>{o.username}</option>)}
        </select>
        
        <div className="flex items-center">
          <button onClick={() => setBidAmount(Math.max(1, bidAmount - 1))} className="w-8 py-2 bg-slate-700 rounded-l">-</button>
          <input type="number" className="flex-1 text-center bg-slate-900 text-xl font-bold border-y border-slate-700 py-1 text-yellow-500" value={bidAmount} onChange={e => setBidAmount(parseInt(e.target.value))} />
          <button onClick={() => setBidAmount(bidAmount + 1)} className="w-8 py-2 bg-slate-700 rounded-r">+</button>
        </div>
        {activeStats && <div className="text-[10px] text-green-400 font-mono mt-1 text-right italic">Max Bid: ${activeStats.maxBid}</div>}
      </div>

      {/* ACTION BUTTONS & TIMER */}
      <div className="md:col-span-3 flex gap-2 h-full">
        <button onClick={handleDraft} className="flex-grow bg-yellow-500 hover:bg-yellow-400 text-black font-black text-xl rounded uppercase shadow-lg transition active:scale-95">
          SOLD! 🔨
        </button>
        <div className="flex flex-col gap-1 w-20">
          <div className={`h-full flex items-center justify-center font-mono text-3xl font-bold border rounded bg-black ${timeLeft <= 3 && isTimerRunning ? 'text-red-500 border-red-500 animate-pulse' : 'text-white border-slate-700'}`}>
            {timeLeft}s
          </div>
          <button onClick={isTimerRunning ? reset : start} className={`text-[10px] py-1 rounded font-bold uppercase ${isTimerRunning ? 'bg-slate-700 text-slate-300' : 'bg-green-600 text-white'}`}>
            {isTimerRunning ? "RESET" : "START"}
          </button>
        </div>
      </div>
    </div>
  );
}