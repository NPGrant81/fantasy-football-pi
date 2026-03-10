// frontend/src/pages/GameCenter.jsx
import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { FiArrowLeft, FiInfo, FiToggleRight, FiToggleLeft } from 'react-icons/fi';
import { EmptyState, LoadingState } from '@components/common/AsyncState';
import TeamLogo from '@components/TeamLogo';
import PageTemplate from '@components/layout/PageTemplate';

// Professional Imports
import apiClient from '@api/client';
import {
  buttonSecondary,
  cardSurface,
  pageShell,
} from '@utils/uiStandards';

// --- 1.1 SUB-COMPONENTS (Declared Outside) ---
// This prevents React from re-creating the component definition on every render.
const RosterColumn = ({ players = [], teamName, teamInfo, colorClass, showProjected }) => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
    <div className="bg-slate-950/50 p-3 border-b border-slate-800 flex items-center gap-2 justify-center">
      <TeamLogo teamInfo={teamInfo} size="sm" />
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
              {showProjected ? p.projected : p.actual}
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

  const initialProjected = (() => {
    if (typeof window === 'undefined') return true;
    const params = new URLSearchParams(window.location.search || '');
    return params.get('view') !== 'actual';
  })();
  const [showProjected, setShowProjected] = useState(initialProjected);

  const syncQueryParam = (projectedState) => {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    url.searchParams.set('view', projectedState ? 'projected' : 'actual');
    window.history.replaceState({}, '', url.toString());
  };

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
  
  const handleToggleChange = () => {
    const newState = !showProjected;
    setShowProjected(newState);
    syncQueryParam(newState);
  };

  const getWinChance = (side) => {
    if (!game) return 50;
    if (side === 'home') return Number(game.home_win_probability ?? 50);
    return Number(game.away_win_probability ?? 50);
  };

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
      <div className={`${pageShell} py-20 text-center`}>
        <LoadingState
          message="Loading matchup data..."
          className="justify-center font-black"
        />
      </div>
    );
  }

  if (!game) {
    return (
      <div className={`${pageShell} py-20 text-center`}>
        <EmptyState
          message="Matchup data unavailable."
          className="justify-center font-black"
        />
      </div>
    );
  }

  return (
    <PageTemplate
      title={`Week ${game.week} Matchup`}
      subtitle={`${showProjected ? 'Projected' : 'Actual'} scoring view with starter breakdown.`}
      className="pb-20 animate-fade-in"
      actions={
        <Link
          to={`/matchups?week=${game.week}&view=${showProjected ? 'projected' : 'actual'}`}
          aria-label="Back to matchups"
          className={`${buttonSecondary} inline-flex w-fit items-center gap-2 px-3 py-1.5 text-xs no-underline`}
        >
          <FiArrowLeft size={16} /> Back
        </Link>
      }
    >

      {/* 2.3 SCOREBOARD BANNER */}
      <div
        className={`${cardSurface} p-8 flex flex-col gap-4 relative overflow-hidden`}
      >
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 via-transparent to-red-600 opacity-50"></div>

        {/* Toggle and Info in Top Right */}
        <div className="absolute top-3 right-3 z-20 flex items-center gap-2">
          <button
            onClick={handleToggleChange}
            aria-label="Toggle projected scores"
            className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-950 border border-slate-700 hover:border-slate-500 transition text-xs"
          >
            <span
              className={`font-bold uppercase ${!showProjected ? 'text-white' : 'text-slate-500'}`}
            >
              Actual
            </span>
            {showProjected ? (
              <FiToggleRight size={20} className="text-blue-400" />
            ) : (
              <FiToggleLeft size={20} className="text-slate-500" />
            )}
            <span
              className={`font-bold uppercase ${showProjected ? 'text-blue-400' : 'text-slate-500'}`}
            >
              Projected
            </span>
          </button>
          
          <div
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
                {showProjected
                  ? 'Projected totals are calculated from each team\'s current starters and your league scoring rules.'
                  : 'Actual scores show real-time or final point totals from completed games.'}
              </div>
            )}
          </div>
        </div>

        {/* Scores Display */}
        <div className="flex justify-between items-center">
          {/* Home Side */}
          <div className="text-center z-10 w-1/3 flex flex-col items-center gap-2">
            <TeamLogo teamInfo={game.home_team_info} size="lg" />
            <h2 className="truncate text-xl font-black tracking-tight text-slate-900 dark:text-white md:text-2xl">
              {game.home_team_info?.team_name || game.home_team}
            </h2>
            <div className={`text-4xl md:text-6xl font-mono font-bold ${showProjected ? 'text-blue-400' : 'text-white'}`}>
              {showProjected ? game.home_projected.toFixed(2) : game.home_score.toFixed(2)}
            </div>
            <div className={`text-xs uppercase font-bold mt-1 ${showProjected ? 'text-blue-500/50' : 'text-slate-500'}`}>
              {showProjected ? 'Projected' : 'Actual'}
            </div>
          </div>

          {/* The Midfield / Divider */}
          <div className="text-center z-10">
            <div className="w-10 h-10 md:w-16 md:h-16 bg-slate-800 rounded-full flex items-center justify-center text-slate-500 font-black italic border border-slate-700 shadow-inner text-sm md:text-xl">
              VS
            </div>
          </div>

          {/* Away Side */}
          <div className="text-center z-10 w-1/3 flex flex-col items-center gap-2">
            <TeamLogo teamInfo={game.away_team_info} size="lg" />
            <h2 className="truncate text-xl font-black tracking-tight text-slate-900 dark:text-white md:text-2xl">
              {game.away_team_info?.team_name || game.away_team}
            </h2>
            <div className={`text-4xl md:text-6xl font-mono font-bold ${showProjected ? 'text-red-400' : 'text-white'}`}>
              {showProjected ? game.away_projected.toFixed(2) : game.away_score.toFixed(2)}
            </div>
            <div className={`text-xs uppercase font-bold mt-1 ${showProjected ? 'text-red-500/50' : 'text-slate-500'}`}>
              {showProjected ? 'Projected' : 'Actual'}
            </div>
          </div>
        </div>

        {showProjected && (
          <div className="mx-auto w-full max-w-2xl rounded-lg border border-slate-700 bg-slate-950/60 p-3">
            <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider">
              <span className="text-blue-300">{getWinChance('home').toFixed(1)}% Win Chance</span>
              <span className="text-red-300">{getWinChance('away').toFixed(1)}% Win Chance</span>
            </div>
            <div
              className="h-3 w-full overflow-hidden rounded-full border border-slate-700 bg-slate-900"
              role="img"
              aria-label="Projected matchup win probability"
            >
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-red-500"
                style={{ width: `${getWinChance('home')}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* 2.4 ROSTERS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative">
        <div className="hidden md:block absolute left-1/2 top-0 bottom-0 w-px bg-slate-800/50 -translate-x-1/2"></div>

        <RosterColumn
          teamName={game.home_team_info?.team_name || game.home_team}
          teamInfo={game.home_team_info}
          players={game.home_roster}
          colorClass={showProjected ? 'text-blue-400' : 'text-white'}
          showProjected={showProjected}
        />

        <RosterColumn
          teamName={game.away_team_info?.team_name || game.away_team}
          teamInfo={game.away_team_info}
          players={game.away_roster}
          colorClass={showProjected ? 'text-red-400' : 'text-white'}
          showProjected={showProjected}
        />
      </div>
    </PageTemplate>
  );
}
