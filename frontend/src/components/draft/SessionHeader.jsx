import { FiClock, FiUsers, FiAlertTriangle } from 'react-icons/fi';

export default function SessionHeader({
  sessionId,
  rosterSize,
  leagueName,
  isCommissioner,
  _leagueId,
  onFinalize,
}) {
  // --- 1.1 SAFETY LOGIC ---
  const handleFinalize = () => {
    if (
      window.confirm(
        'WARNING: This will finalize all picks and close the auction. Proceed?'
      )
    ) {
      onFinalize();
    }
  };

  // --- 2.1 RENDER LOGIC (The View) ---
  return (
    <div className="flex justify-between items-center py-2 bg-slate-950 border border-slate-800 rounded-lg px-4 mb-6 shadow-inner uppercase tracking-[0.2em] text-[9px] font-black">
      {/* 2.2 METADATA GROUP */}
      <div className="flex gap-8 items-center">
        <div className="flex items-center gap-2 group">
          <FiClock className="text-purple-500 group-hover:scale-110 transition-transform" />
          <span className="text-slate-500">
            Session ID:{' '}
            <span className="text-purple-400 font-mono ml-1">{sessionId}</span>
          </span>
        </div>

        <div className="flex items-center gap-2 group">
          <FiUsers className="text-blue-500 group-hover:scale-110 transition-transform" />
          <span className="text-slate-500">
            Roster Limit:{' '}
            <span className="text-blue-400 font-mono ml-1">{rosterSize}</span>
          </span>
        </div>
        {leagueName && (
          <div className="flex items-center gap-2 group">
            <span className="text-yellow-400 font-black">{leagueName}</span>
          </div>
        )}
      </div>

      {/* 2.3 ADMINISTRATIVE ACTIONS */}
      {isCommissioner && (
        <button
          onClick={handleFinalize}
          className="group flex items-center gap-2 bg-red-950/40 hover:bg-red-600 border border-red-900/50 hover:border-red-400 text-red-500 hover:text-white px-4 py-1.5 rounded-full transition-all duration-300"
        >
          <FiAlertTriangle className="text-xs group-hover:animate-bounce" />
          <span className="tracking-widest">End Draft Session</span>
        </button>
      )}
    </div>
  );
}
