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
  nominatorId,
  setOverrideNominator,
  isCommissioner,
}) {
  // --- 1.1 LOGIC ---
  const nominator = owners.find((o) => o.id === nominatorId);
  const nominatorName = nominator
    ? nominator.team_name || nominator.username
    : 'TBD';

  const isOverBudget = activeStats && bidAmount > activeStats.maxBid;
  const canDraft = playerName && winnerId && !isOverBudget;
  const maxBid = activeStats ? activeStats.maxBid : 0;

  // --- 2.1 RENDER ---
  return (
    <div className="flex flex-col gap-6 w-full">
      {/* top row */}
      <div className="flex justify-between items-center text-[12px] text-slate-300">
        <div className="flex items-center gap-2">
          <span className="font-semibold">Nominator:</span>
          {isCommissioner ? (
            <select
              value={nominatorId || ''}
              onChange={(e) =>
                setOverrideNominator?.(parseInt(e.target.value) || null)
              }
              className="bg-slate-900 text-white border border-slate-700 rounded p-1 text-sm"
            >
              <option value="" disabled>
                select owner
              </option>
              {owners.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.team_name || o.username}
                </option>
              ))}
            </select>
          ) : (
            <span className="font-bold text-yellow-400">{nominatorName}</span>
          )}
          {isCommissioner && (
            <span className="ml-2 text-red-400 uppercase font-black">
              ADMIN
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div
            className={`w-16 font-mono text-2xl font-bold text-center ${
              timeLeft <= 3 && isTimerRunning
                ? 'text-red-500 animate-pulse'
                : 'text-white'
            }`}
          >
            {timeLeft}
          </div>
          <button
            onClick={isTimerRunning ? reset : start}
            className={`text-[10px] py-2 px-3 rounded font-black uppercase transition ${
              isTimerRunning
                ? 'bg-slate-700 text-slate-300 hover:bg-red-900/40'
                : 'bg-green-600 text-white hover:bg-green-500'
            }`}
          >
            {isTimerRunning ? 'RESET' : 'START'}
          </button>
        </div>
      </div>

      {/* search/filter area */}
      <div className="relative w-full">
        <div className="flex flex-wrap gap-1 mb-2">
          {['ALL', ...POSITIONS].map((pos) => (
            <button
              key={pos}
              onClick={() => setPosFilter(pos)}
              className={`text-[10px] font-bold px-3 py-1 rounded border transition uppercase ${
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
          <ul className="absolute z-50 w-full bg-slate-900 border border-slate-700 mt-1 rounded-lg shadow-2xl max-h-60 overflow-y-auto">
            {suggestions.map((p) => (
              <li
                key={p.id}
                onClick={() => selectSuggestion(p)}
                className="p-3 hover:bg-slate-800 cursor-pointer flex justify-between items-center border-b border-slate-800 last:border-0"
              >
                <span className="font-bold text-slate-200">{p.name}</span>
                <div className="flex items-center gap-2">
                  {p.espn_id && (
                    <span className="text-[9px] uppercase tracking-widest text-slate-400 border border-slate-700 px-2 py-0.5 rounded">
                      ESPN
                    </span>
                  )}
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded font-black border ${getPosColor(p.position)}`}
                  >
                    {normalizePos(p.position)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* bidding block */}
      <div className="bg-slate-800/30 border border-slate-700 p-4 rounded w-full">
        <label className="block text-slate-500 text-[10px] uppercase font-black mb-2">
          Winning Bidder
        </label>
        <select
          className="w-full bg-slate-900 text-white border border-slate-700 rounded p-1.5 text-sm font-bold mb-4 outline-none focus:border-yellow-500"
          value={owners.some((o) => o.id === winnerId) ? winnerId : ''}
          onChange={(e) => setWinnerId(parseInt(e.target.value))}
          disabled={owners.length === 0}
        >
          <option value="" disabled>
            {owners.length === 0 ? 'No owners available' : 'Select Owner'}
          </option>
          {owners.map((o) => (
            <option key={o.id} value={o.id}>
              {o.team_name ? `${o.team_name} — ${o.username}` : o.username}
            </option>
          ))}
        </select>

        {/* quick bids */}
        <div className="flex gap-2 mb-3">
          <button
            onClick={() => setBidAmount(Math.min(maxBid, bidAmount + 1))}
            className="flex-1 bg-slate-700 hover:bg-slate-600 text-white py-2 rounded font-bold"
          >
            +$1
          </button>
          <button
            onClick={() => setBidAmount(Math.min(maxBid, bidAmount + 5))}
            className="flex-1 bg-slate-700 hover:bg-slate-600 text-white py-2 rounded font-bold"
          >
            +$5
          </button>
          <button
            onClick={() => setBidAmount(maxBid)}
            disabled={bidAmount >= maxBid}
            className="flex-1 bg-red-900 hover:bg-red-600 text-white py-2 rounded font-bold disabled:opacity-50"
          >
            MAX
          </button>
        </div>

        {/* manual adjustment */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setBidAmount(Math.max(MIN_BID, bidAmount - 1))}
            className="w-16 h-12 bg-slate-700 hover:bg-slate-600 text-white rounded font-bold text-2xl"
          >
            -
          </button>
          <input
            type="number"
            className="flex-1 text-center bg-slate-950 text-2xl font-mono font-bold border-y border-slate-700 py-2"
            value={bidAmount}
            onChange={(e) => setBidAmount(parseInt(e.target.value) || MIN_BID)}
          />
          <button
            onClick={() => setBidAmount(bidAmount + 1)}
            className="w-16 h-12 bg-slate-700 hover:bg-slate-600 text-white rounded font-bold text-2xl"
          >
            +
          </button>
        </div>

        {activeStats && (
          <div className="text-[10px] font-mono mt-3 text-right">
            Available: ${activeStats.budget} | Max Bid: ${activeStats.maxBid}
          </div>
        )}
      </div>

      {/* sold button row */}
      <div className="flex justify-center">
        <button
          onClick={handleDraft}
          disabled={!canDraft}
          className="w-full bg-yellow-500 hover:bg-yellow-400 text-black font-black text-xl py-3 rounded disabled:opacity-40"
        >
          SOLD! 🔨
        </button>
      </div>
    </div>
  ); // end root container
}
