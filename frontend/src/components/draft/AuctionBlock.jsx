import { useRef } from 'react';
import { POSITIONS, normalizePos, MIN_BID } from '@utils';
import { getPosColor } from '../../utils/uiHelpers';
import FloatingLayer from '@components/overlay/FloatingLayer';

export default function AuctionBlock({
  // control flags
  leftOnly = false,
  centerOnly = false,
  // optional sidebar toggle integration
  showBestSidebar,
  toggleSidebar,
  // the rest are the usual props
  playerName,
  handleSearchChange,
  suggestions,
  showSuggestions,
  selectSuggestion,
  positions = POSITIONS,
  posFilter,
  setPosFilter,
  winnerId,
  setWinnerId,
  owners = [],
  activeStats,
  ownerStatsById = {},
  bidAmount,
  setBidAmount,
  handleDraft,
  canDraft: canDraftProp,
  timeLeft,
  isTimerRunning,
  reset,
  start,
  nominatorId,
  setOverrideNominator,
  isCommissioner,
  lastDraftedText,
}) {
  const suggestionsAnchorRef = useRef(null);

  // --- 1.1 LOGIC ---
  const nominator = owners.find((o) => o.id === nominatorId);
  const nominatorName = nominator
    ? nominator.team_name || nominator.username
    : 'TBD';

  const selectedOwnerStats = ownerStatsById[winnerId] || activeStats || null;
  const isOverBudget =
    selectedOwnerStats && bidAmount > selectedOwnerStats.maxBid;
  const isWinnerFull = selectedOwnerStats?.isFull;
  const canDraft = Boolean(
    (canDraftProp ?? (playerName && winnerId)) && !isOverBudget && !isWinnerFull
  );
  const maxBid = selectedOwnerStats ? selectedOwnerStats.maxBid : 0;

  const getOwnerOptionMeta = (ownerId) => {
    const stats = ownerStatsById[ownerId];
    if (!stats) return { disabled: false, suffix: '' };
    if (stats.isFull) {
      return { disabled: true, suffix: ' (FULL)' };
    }
    if (bidAmount > stats.maxBid) {
      return { disabled: true, suffix: ` (MAX $${stats.maxBid})` };
    }
    return { disabled: false, suffix: '' };
  };

  // --- 2.1 RENDER ---
  // if only the left portion is requested, render nominator/search/timer panel
  if (leftOnly) {
    const nominator = owners.find((o) => o.id === nominatorId);
    const nominatorName = nominator
      ? nominator.team_name || nominator.username
      : 'TBD';
    return (
      <div className="flex flex-col gap-2 text-[12px] text-slate-300">
        {/* position filter row */}
        <div className="flex flex-wrap gap-1">
          {['ALL', ...positions].map((pos) => (
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
        {/* search input */}
        <input
          className="w-40 p-1 rounded bg-slate-950 border border-slate-700 text-sm outline-none focus:border-yellow-500"
          value={playerName}
          onChange={handleSearchChange}
          placeholder="Nominate Player..."
        />
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
        <div className="flex items-center gap-2 ml-4">
          <div
            className={`w-12 font-mono text-xl font-bold text-center ${
              timeLeft <= 3 && isTimerRunning
                ? 'text-red-500 animate-pulse'
                : 'text-white'
            }`}
          >
            {timeLeft}
          </div>
          <button
            onClick={isTimerRunning ? reset : start}
            className={`text-[10px] py-1 px-2 rounded font-black uppercase transition ${
              isTimerRunning
                ? 'bg-slate-700 text-slate-300 hover:bg-red-900/40'
                : 'bg-green-600 text-white hover:bg-green-500'
            }`}
          >
            {isTimerRunning ? 'RESET' : 'START'}
          </button>
        </div>
      </div>
    );
  }

  // if only the center bidding modal is needed
  if (centerOnly) {
    const nominator = owners.find((o) => o.id === nominatorId);
    const nominatorName = nominator
      ? nominator.team_name || nominator.username
      : 'TBD';
    return (
      <div className="bg-slate-800/30 border border-slate-700 p-4 rounded w-[320px]">
        <div className="mb-2">
          <span className="text-sm">Nominator:</span>{' '}
          <span className="font-bold text-yellow-400">{nominatorName}</span>
        </div>
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
            <option
              key={o.id}
              value={o.id}
              disabled={getOwnerOptionMeta(o.id).disabled}
            >
              {(o.team_name ? `${o.team_name} — ${o.username}` : o.username) +
                getOwnerOptionMeta(o.id).suffix}
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
            onClick={() => setBidAmount(Math.max(MIN_BID, maxBid))}
            disabled={bidAmount >= maxBid}
            className="flex-1 bg-red-900 hover:bg-red-600 text-white py-2 rounded font-bold disabled:opacity-50"
          >
            MAX
          </button>
        </div>

        {/* manual adjustment and slider omitted for brevity */}
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
            onChange={(e) => {
              const next = parseInt(e.target.value, 10);
              if (Number.isNaN(next)) {
                setBidAmount(MIN_BID);
                return;
              }
              setBidAmount(
                Math.max(MIN_BID, Math.min(maxBid || MIN_BID, next))
              );
            }}
          />
        </div>
      </div>
    );
  }

  // --- previous full render ---
  return (
    <div className="flex flex-col w-full">
      <div
        data-testid="auction-top-row"
        className="grid grid-cols-1 xl:grid-cols-12 gap-0 w-full overflow-hidden border border-slate-700 rounded"
      >
        <div className="xl:col-span-4 border-b xl:border-b-0 xl:border-r border-slate-700 bg-slate-900/40 p-2">
          <div className="flex items-center justify-between text-slate-200 text-sm mb-2">
            <span className="font-semibold">Nominating Team</span>
            <span className="font-bold text-white">{nominatorName}</span>
          </div>
          <div className="flex flex-wrap gap-1 mb-2">
            {['ALL', ...positions].map((pos) => (
              <button
                key={pos}
                onClick={() => setPosFilter(pos)}
                className={`text-xs font-bold px-4 py-2 rounded border transition uppercase ${
                  posFilter === pos
                    ? 'bg-yellow-500 text-black border-yellow-500'
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
                }`}
              >
                {pos}
              </button>
            ))}
          </div>
          <div ref={suggestionsAnchorRef} className="relative min-w-0">
            <input
              className="w-full p-3 rounded bg-slate-950 border border-slate-700 text-lg font-bold outline-none focus:border-yellow-500 transition-colors"
              value={playerName}
              onChange={handleSearchChange}
              placeholder="Nominate Player..."
            />
            {showSuggestions && suggestions.length > 0 && (
              <FloatingLayer
                anchorRef={suggestionsAnchorRef}
                open={showSuggestions && suggestions.length > 0}
                offset={4}
                className="bg-slate-900 border border-slate-700 rounded-lg shadow-2xl max-h-60 overflow-y-auto"
              >
                <ul>
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
              </FloatingLayer>
            )}
          </div>
        </div>

        <div className="xl:col-span-3 border-b xl:border-b-0 xl:border-r border-slate-700 bg-slate-900/40 p-2">
          <label className="block text-slate-500 text-[10px] uppercase font-black mb-2">
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
              <option
                key={o.id}
                value={o.id}
                disabled={getOwnerOptionMeta(o.id).disabled}
              >
                {(o.team_name ? `${o.team_name} — ${o.username}` : o.username) +
                  getOwnerOptionMeta(o.id).suffix}
              </option>
            ))}
          </select>

          <div className="flex gap-2 mb-2">
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
              onClick={() => setBidAmount(Math.max(MIN_BID, maxBid))}
              disabled={bidAmount >= maxBid}
              className="flex-1 bg-red-900 hover:bg-red-600 text-white py-2 rounded font-bold disabled:opacity-50"
            >
              MAX
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setBidAmount(Math.max(MIN_BID, bidAmount - 1))}
              className="w-10 h-10 bg-slate-700 hover:bg-slate-600 text-white rounded font-bold text-2xl"
            >
              -
            </button>
            <input
              type="number"
              className="flex-1 text-center bg-slate-950 text-2xl font-mono font-bold border-y border-slate-700 py-1"
              value={bidAmount}
              onChange={(e) => {
                const next = parseInt(e.target.value, 10);
                if (Number.isNaN(next)) {
                  setBidAmount(MIN_BID);
                  return;
                }
                setBidAmount(
                  Math.max(MIN_BID, Math.min(maxBid || MIN_BID, next))
                );
              }}
            />
            <button
              onClick={() =>
                setBidAmount(Math.min(maxBid || MIN_BID, bidAmount + 1))
              }
              className="w-10 h-10 bg-slate-700 hover:bg-slate-600 text-white rounded font-bold text-2xl"
            >
              +
            </button>
          </div>

          {activeStats && (
            <div className="text-[10px] font-mono mt-2 text-right">
              Available: ${activeStats.budget} | Max Bid: ${activeStats.maxBid}
            </div>
          )}
          {selectedOwnerStats?.isFull && (
            <div className="mt-2 text-[10px] font-mono text-right text-red-400">
              Selected owner roster is full.
            </div>
          )}
          {!selectedOwnerStats?.isFull && isOverBudget && (
            <div className="mt-2 text-[10px] font-mono text-right text-red-400">
              Bid exceeds selected owner max (${selectedOwnerStats?.maxBid ?? 0}).
            </div>
          )}
        </div>

        <div className="xl:col-span-2 border-b xl:border-b-0 xl:border-r border-slate-700 bg-slate-900/40 p-2 flex flex-col">
          <div className="text-slate-200 text-[13px] font-semibold mb-2">Draft Timer</div>
          <div className="flex items-center justify-between gap-2">
            {isCommissioner && (
              <span className="text-red-400 uppercase font-black text-sm">ADMIN</span>
            )}
            <div
              className={`font-mono text-4xl font-black text-center min-w-[48px] ${
                timeLeft <= 3 && isTimerRunning
                  ? 'text-red-500 animate-pulse'
                  : 'text-white'
              }`}
            >
              {timeLeft}
            </div>
            <button
              onClick={isTimerRunning ? reset : start}
              className={`text-[11px] py-2 px-3 rounded font-black uppercase transition ${
                isTimerRunning
                  ? 'bg-slate-700 text-slate-300 hover:bg-red-900/40'
                  : 'bg-green-600 text-white hover:bg-green-500'
              }`}
            >
              {isTimerRunning ? 'RESET' : 'START'}
            </button>
          </div>

          <button
            onClick={handleDraft}
            disabled={!canDraft}
            className="mt-2 w-full bg-yellow-500 hover:bg-yellow-400 text-black font-black text-xl py-3 rounded disabled:opacity-40 flex items-center justify-center gap-2"
          >
            <span>SOLD!</span>
            <span role="img" aria-label="gavel" className="text-xl">
              🔨
            </span>
          </button>
        </div>

        <div className="xl:col-span-2 border-b xl:border-b-0 xl:border-r border-slate-700 bg-slate-900/40 p-3 flex items-center">
          <p className="text-amber-400 text-xl leading-tight font-medium">
            &lt;Pop-up: {lastDraftedText || '"Player Name" drafted to "Team Name" for "$XX"'}&gt;
          </p>
        </div>

        {typeof toggleSidebar === 'function' && (
          <div className="xl:col-span-1 flex bg-slate-900/40">
            <button
              onClick={() => toggleSidebar(!showBestSidebar)}
              className="w-full min-h-[112px] px-4 py-3 rounded-none bg-slate-200 text-slate-900 text-3xl xl:text-2xl leading-tight font-medium whitespace-pre-line"
            >
              {showBestSidebar ? 'Hide\nBest' : 'Show\nBest\nAvailable'}
            </button>
          </div>
        )}
      </div>

    </div>
  ); // end root container
}
