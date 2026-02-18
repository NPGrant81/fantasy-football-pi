import { POSITIONS, normalizePos, MIN_BID } from '@utils';
import { getPosColor } from '../../utils/uiHelpers';

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
  start,
}) {
  // --- 1.1 VALIDATION LOGIC ---
  // Prevent bidding more than the owner's calculated Max Bid from draftHelpers
  const isOverBudget = activeStats && bidAmount > activeStats.maxBid;
  const canDraft = playerName && winnerId && !isOverBudget;

  // --- 2.1 RENDER LOGIC (The View) ---
  return (
    <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
      {/* 2.2 SEARCH & FILTERS */}
      <div className="md:col-span-5 relative">
        <div className="flex gap-1 mb-2 overflow-x-auto no-scrollbar">
          {['ALL', ...POSITIONS].map((pos) => (
            <button
              key={pos}
              onClick={() => setPosFilter(pos)}
              className={`text-[10px] font-bold px-2 py-1 rounded border transition uppercase ${
                posFilter === pos
                  ? 'bg-yellow-500 text-black border-yellow-500'
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
              }`}
            >
              {pos}
            </button>
          ))}
        </div>
        <input
          className="w-full p-3 rounded bg-slate-950 border border-slate-700 text-lg font-bold outline-none focus:border-yellow-500 transition-colors"
          value={playerName}
          onChange={handleSearchChange}
          placeholder="Nominate Player..."
        />

        {showSuggestions && suggestions.length > 0 && (
          <ul className="absolute z-50 w-full bg-slate-900 border border-slate-700 mt-1 rounded-lg shadow-2xl max-h-60 overflow-y-auto border-t-0 rounded-t-none">
            {suggestions.map((p) => (
              <li
                key={p.id}
                onClick={() => selectSuggestion(p)}
                className="p-3 hover:bg-slate-800 cursor-pointer flex justify-between items-center border-b border-slate-800 last:border-0 transition"
              >
                <span className="font-bold text-slate-200">{p.name}</span>
                <span
                  className={`text-[10px] px-2 py-0.5 rounded font-black border ${getPosColor(p.position)}`}
                >
                  {normalizePos(p.position)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 2.3 BIDDING & STATS */}
      <div
        className={`md:col-span-4 p-2 rounded border transition-colors ${isOverBudget ? 'bg-red-900/10 border-red-900/50' : 'bg-slate-800/30 border-slate-700'}`}
      >
        <label className="block text-slate-500 text-[10px] uppercase font-black mb-1 tracking-widest">
          Winning Bidder
        </label>
        <select
          className="w-full bg-slate-900 text-white border border-slate-700 rounded p-1.5 text-sm font-bold mb-2 outline-none focus:border-yellow-500"
          value={owners.some((o) => o.id === winnerId) ? winnerId : ''}
          onChange={(e) => setWinnerId(parseInt(e.target.value))}
          disabled={owners.length === 0}
        >
          <option value="" disabled>
            {owners.length === 0 ? 'No owners available' : 'Select Owner'}
          </option>
          {owners.map((o) => (
            <option key={o.id} value={o.id}>
              {o.username}
            </option>
          ))}
        </select>

        <div className="flex items-center">
          <button
            onClick={() => setBidAmount(Math.max(MIN_BID, bidAmount - 1))}
            className="w-10 py-2 bg-slate-700 rounded-l hover:bg-slate-600 transition"
          >
            -
          </button>
          <input
            type="number"
            className={`flex-1 text-center bg-slate-950 text-xl font-mono font-bold border-y border-slate-700 py-1 ${isOverBudget ? 'text-red-500' : 'text-yellow-500'}`}
            value={bidAmount}
            onChange={(e) => setBidAmount(parseInt(e.target.value) || MIN_BID)}
          />
          <button
            onClick={() => setBidAmount(bidAmount + 1)}
            className="w-10 py-2 bg-slate-700 rounded-r hover:bg-slate-600 transition"
          >
            +
          </button>
        </div>
        {activeStats && (
          <div
            className={`text-[10px] font-mono mt-1.5 text-right flex justify-between px-1`}
          >
            <span className="text-slate-500 uppercase">
              Available: ${activeStats.budget}
            </span>
            <span
              className={
                isOverBudget
                  ? 'text-red-500 font-bold animate-pulse'
                  : 'text-green-400 italic'
              }
            >
              {isOverBudget
                ? 'EXCEEDS MAX BID'
                : `Max Bid: $${activeStats.maxBid}`}
            </span>
          </div>
        )}
      </div>

      {/* 2.4 ACTIONS & TIMER */}
      <div className="md:col-span-3 flex gap-2 h-[84px]">
        <button
          onClick={handleDraft}
          disabled={!canDraft}
          className={`flex-grow font-black text-xl rounded uppercase shadow-lg transition transform active:scale-95 disabled:opacity-20 disabled:cursor-not-allowed disabled:grayscale ${
            canDraft
              ? 'bg-yellow-500 hover:bg-yellow-400 text-black'
              : 'bg-slate-700 text-slate-500'
          }`}
        >
          SOLD! 🔨
        </button>

        <div className="flex flex-col gap-1 w-20">
          <div
            className={`h-full flex items-center justify-center font-mono text-3xl font-bold border rounded bg-black shadow-inner ${
              timeLeft <= 3 && isTimerRunning
                ? 'text-red-500 border-red-500 animate-pulse'
                : 'text-white border-slate-700'
            }`}
          >
            {timeLeft}
          </div>
          <button
            onClick={isTimerRunning ? reset : start}
            className={`text-[10px] py-1 rounded font-black uppercase transition ${
              isTimerRunning
                ? 'bg-slate-700 text-slate-300 hover:bg-red-900/40'
                : 'bg-green-600 text-white hover:bg-green-500'
            }`}
          >
            {isTimerRunning ? 'RESET' : 'START'}
          </button>
        </div>
      </div>
    </div>
  );
}
