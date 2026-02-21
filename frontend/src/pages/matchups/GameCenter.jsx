// frontend/src/pages/GameCenter.jsx
import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { FiArrowLeft, FiInfo } from 'react-icons/fi';

// Professional Imports
import apiClient from '@api/client';

// --- 1.1 SUB-COMPONENTS (Declared Outside) ---
// This prevents React from re-creating the component definition on every render.
const RosterColumn = ({ players = [], teamName, colorClass }) => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
    <div className="bg-slate-950/50 p-3 border-b border-slate-800 text-center">
      <h3 className="font-bold text-slate-400 uppercase tracking-widest text-xs">
        {teamName} Starters
      </h3>
    </div>
    <div className="divide-y divide-slate-800">
      {players.length === 0 ? (
        <div className="p-8 text-center text-slate-600 italic text-sm">
          No starters set.
        </div>
      ) : (
        players.map((p) => (
          <div
            key={p.player_id}
            className="flex justify-between items-center p-3 hover:bg-slate-800/30 transition"
          >
            <div className="flex items-center gap-3">
              <span
                className={`text-[10px] font-bold px-1.5 py-0.5 rounded w-8 text-center ${
                  p.position === 'QB'
                    ? 'bg-red-900/20 text-red-400 border border-red-900/50'
                    : p.position === 'RB'
                      ? 'bg-green-900/20 text-green-400 border border-green-900/50'
                      : p.position === 'WR'
                        ? 'bg-blue-900/20 text-blue-400 border border-blue-900/50'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                }`}
              >
                {p.position}
              </span>
              <div>
                <div className="text-sm font-bold text-slate-200">{p.name}</div>
                <div className="text-[10px] text-slate-500">{p.nfl_team}</div>
              </div>
            </div>
            <div className={`font-mono font-bold ${colorClass}`}>
              {p.projected}
            </div>
          </div>
        ))
      )}
    </div>
  </div>
);

export default function GameCenter() {
  // --- 1.2 STATE & PARAMS ---
  const { id } = useParams();
  const [game, setGame] = useState(null);
  const [showScoreInfo, setShowScoreInfo] = useState(false);

  useEffect(() => {
    if (!showScoreInfo) return;

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setShowScoreInfo(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showScoreInfo]);

  // Start with loading: true to avoid synchronous setState inside useEffect
  const [loading, setLoading] = useState(true);

  // --- 1.3 DATA RETRIEVAL (The Engine) ---
  useEffect(() => {
    if (id) {
      // 1.3.1 Using centralized client; token is handled by interceptors
      apiClient
        .get(`/matchups/${id}`)
        .then((res) => {
          setGame(res.data);
        })
        .catch((err) => {
          console.error('Matchup fetch failed:', err);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [id]);

  // --- 2.1 RENDER LOGIC (The View) ---

  // 2.1.1 Handle Loading & Empty States
  if (loading) {
    return (
      <div className="text-center py-20 text-slate-500 animate-pulse font-black uppercase tracking-widest">
        Loading Matchup Data...
      </div>
    );
  }

  if (!game) {
    return (
      <div className="text-center py-20 text-slate-500 font-black uppercase tracking-widest">
        Matchup data unavailable.
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-20 animate-fade-in">
      {/* 2.2 HEADER & NAVIGATION */}
      <div className="flex items-center gap-4">
        <Link
          to="/matchups"
          aria-label="Back to matchups"
          className="p-2 bg-slate-800 rounded-full text-slate-400 hover:text-white hover:bg-slate-700 transition shadow-lg"
        >
          <FiArrowLeft size={20} />
        </Link>
        <h1 className="text-xl font-bold text-slate-300 uppercase tracking-wide">
          Week {game.week} Matchup
        </h1>
      </div>

      {/* 2.3 SCOREBOARD BANNER */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-2xl flex justify-between items-center relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 via-transparent to-red-600 opacity-50"></div>

        <div
          className="absolute top-3 right-3 z-20"
          onMouseEnter={() => setShowScoreInfo(true)}
          onMouseLeave={() => setShowScoreInfo(false)}
        >
          <button
            type="button"
            onClick={() => setShowScoreInfo((prev) => !prev)}
            aria-label="Explain scoring values"
            aria-expanded={showScoreInfo}
            className="h-8 w-8 rounded-full bg-slate-950 border border-slate-700 text-slate-400 hover:text-white hover:border-slate-500 transition flex items-center justify-center"
          >
            <FiInfo size={14} />
          </button>
          {showScoreInfo && (
            <div className="absolute right-0 mt-2 w-72 rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs text-slate-300 shadow-xl">
              Projected totals are calculated from each team&apos;s current
              starters and your league scoring rules.
            </div>
          )}
        </div>

        {/* Home Side */}
        <div className="text-center z-10 w-1/3">
          <h2 className="text-xl md:text-3xl font-black text-white italic tracking-tighter uppercase mb-2 truncate">
            {game.home_team}
          </h2>
          <div className="text-4xl md:text-6xl font-mono font-bold text-blue-400">
            {game.home_projected.toFixed(2)}
          </div>
          <div className="text-xs text-blue-500/50 uppercase font-bold mt-1">
            Projected
          </div>
        </div>

        {/* The Midfield / Divider */}
        <div className="text-center z-10">
          <div className="w-10 h-10 md:w-16 md:h-16 bg-slate-800 rounded-full flex items-center justify-center text-slate-500 font-black italic border border-slate-700 shadow-inner text-sm md:text-xl">
            VS
          </div>
        </div>

        {/* Away Side */}
        <div className="text-center z-10 w-1/3">
          <h2 className="text-xl md:text-3xl font-black text-white italic tracking-tighter uppercase mb-2 truncate">
            {game.away_team}
          </h2>
          <div className="text-4xl md:text-6xl font-mono font-bold text-red-400">
            {game.away_projected.toFixed(2)}
          </div>
          <div className="text-xs text-red-500/50 uppercase font-bold mt-1">
            Projected
          </div>
        </div>
      </div>

      {/* 2.4 ROSTERS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative">
        <div className="hidden md:block absolute left-1/2 top-0 bottom-0 w-px bg-slate-800/50 -translate-x-1/2"></div>

        <RosterColumn
          teamName={game.home_team}
          players={game.home_roster}
          colorClass="text-blue-400"
        />

        <RosterColumn
          teamName={game.away_team}
          players={game.away_roster}
          colorClass="text-red-400"
        />
      </div>
    </div>
  );
}
