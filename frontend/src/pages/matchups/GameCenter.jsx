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
  <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-800 dark:bg-slate-900">
    <div className="flex items-center justify-center gap-2 border-b border-slate-200 bg-slate-100 p-3 dark:border-slate-800 dark:bg-slate-950/50">
      <TeamLogo teamInfo={teamInfo} size="sm" />
      <h3 className="text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-400">
        {teamName} Starters
      </h3>
    </div>
    <div className="divide-y divide-slate-200 dark:divide-slate-800">
      {players.length === 0 ? (
        <div className="p-8 text-center text-sm italic text-slate-500 dark:text-slate-600">
          No starters set.
        </div>
      ) : (
        players.map((p) => (
          <div
            key={p.player_id}
            className="flex items-center justify-between p-3 transition hover:bg-slate-100 dark:hover:bg-slate-800/30"
          >
            <div className="flex items-center gap-3">
              <span
                className={`text-[10px] font-bold px-1.5 py-0.5 rounded w-8 text-center ${
                  p.position === 'QB'
                    ? 'border border-red-400/60 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-900/20 dark:text-red-400'
                    : p.position === 'RB'
                      ? 'border border-green-400/60 bg-green-50 text-green-700 dark:border-green-900/50 dark:bg-green-900/20 dark:text-green-400'
                      : p.position === 'WR'
                        ? 'border border-blue-400/60 bg-blue-50 text-blue-700 dark:border-blue-900/50 dark:bg-blue-900/20 dark:text-blue-400'
                        : 'border border-slate-300 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400'
                }`}
              >
                {p.position}
              </span>
              <div>
                <div className="text-sm font-bold text-slate-900 dark:text-slate-200">{p.name}</div>
                <div className="text-[10px] text-slate-500 dark:text-slate-400">{p.nfl_team}</div>
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

  const selectedWeek = (() => {
    if (typeof window === 'undefined') return game.week;
    const params = new URLSearchParams(window.location.search || '');
    const parsedWeek = parseInt(params.get('week'), 10);
    return parsedWeek >= 1 && parsedWeek <= 17 ? parsedWeek : game.week;
  })();

  return (
    <PageTemplate className="pb-20 animate-fade-in">
      <div className="mb-4 flex justify-end">
        <Link
          to={`/matchups?week=${selectedWeek}&view=${showProjected ? 'projected' : 'actual'}`}
          aria-label="Back to matchups"
          className={`${buttonSecondary} inline-flex w-fit items-center gap-2 px-3 py-1.5 text-xs no-underline`}
        >
          <FiArrowLeft size={16} /> Back
        </Link>
      </div>

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
            className="flex items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs transition hover:border-slate-500 dark:border-slate-700 dark:bg-slate-950"
          >
            <span
              className={`font-bold uppercase ${!showProjected ? 'text-slate-900 dark:text-white' : 'text-slate-500'}`}
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
              className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-500 transition hover:border-slate-500 hover:text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400 dark:hover:text-white"
            >
              <FiInfo size={14} />
            </button>
            {showScoreInfo && (
              <div className="absolute right-0 mt-2 w-72 rounded-lg border border-slate-300 bg-white p-3 text-xs text-slate-700 shadow-xl dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300">
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
            <div className={`text-4xl md:text-6xl font-mono font-bold ${showProjected ? 'text-blue-500 dark:text-blue-400' : 'text-slate-900 dark:text-white'}`}>
              {showProjected ? game.home_projected.toFixed(2) : game.home_score.toFixed(2)}
            </div>
            <div className={`text-xs uppercase font-bold mt-1 ${showProjected ? 'text-blue-500/50' : 'text-slate-500'}`}>
              {showProjected ? 'Projected' : 'Actual'}
            </div>
          </div>

          {/* The Midfield / Divider */}
          <div className="text-center z-10">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-300 bg-slate-100 text-sm font-black italic text-slate-500 shadow-inner md:h-16 md:w-16 md:text-xl dark:border-slate-700 dark:bg-slate-800">
              VS
            </div>
          </div>

          {/* Away Side */}
          <div className="text-center z-10 w-1/3 flex flex-col items-center gap-2">
            <TeamLogo teamInfo={game.away_team_info} size="lg" />
            <h2 className="truncate text-xl font-black tracking-tight text-slate-900 dark:text-white md:text-2xl">
              {game.away_team_info?.team_name || game.away_team}
            </h2>
            <div className={`text-4xl md:text-6xl font-mono font-bold ${showProjected ? 'text-red-500 dark:text-red-400' : 'text-slate-900 dark:text-white'}`}>
              {showProjected ? game.away_projected.toFixed(2) : game.away_score.toFixed(2)}
            </div>
            <div className={`text-xs uppercase font-bold mt-1 ${showProjected ? 'text-red-500/50' : 'text-slate-500'}`}>
              {showProjected ? 'Projected' : 'Actual'}
            </div>
          </div>
        </div>

        {showProjected && (
          <div className="mx-auto w-full max-w-2xl rounded-lg border border-slate-300 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-950/60">
            <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider">
              <span className="text-blue-600 dark:text-blue-300">{getWinChance('home').toFixed(1)}% Win Chance</span>
              <span className="text-red-600 dark:text-red-300">{getWinChance('away').toFixed(1)}% Win Chance</span>
            </div>
            <div
              className="h-3 w-full overflow-hidden rounded-full border border-slate-300 bg-slate-100 dark:border-slate-700 dark:bg-slate-900"
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
        <div className="absolute left-1/2 top-0 bottom-0 hidden w-px -translate-x-1/2 bg-slate-300/70 dark:bg-slate-800/50 md:block"></div>

        <RosterColumn
          teamName={game.home_team_info?.team_name || game.home_team}
          teamInfo={game.home_team_info}
          players={game.home_roster}
          colorClass={showProjected ? 'text-blue-600 dark:text-blue-400' : 'text-slate-900 dark:text-white'}
          showProjected={showProjected}
        />

        <RosterColumn
          teamName={game.away_team_info?.team_name || game.away_team}
          teamInfo={game.away_team_info}
          players={game.away_roster}
          colorClass={showProjected ? 'text-red-600 dark:text-red-400' : 'text-slate-900 dark:text-white'}
          showProjected={showProjected}
        />
      </div>
    </PageTemplate>
  );
}
