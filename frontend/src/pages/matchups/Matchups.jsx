// frontend/src/pages/Matchups.jsx
import { useEffect, useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  FiChevronLeft,
  FiChevronRight,
  FiCalendar,
  FiActivity,
  FiToggleRight,
  FiToggleLeft,
  FiInfo,
  FiInbox,
} from 'react-icons/fi';
import TeamLogo from '@components/TeamLogo';

// Professional Imports
import apiClient from '@api/client';
import {
  buttonSecondary,
  cardSurface,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '@utils/uiStandards';

export default function Matchups() {
  // --- USER/LEAGUE CONTEXT ---
  const [userInfo, setUserInfo] = useState({ username: '', leagueName: '' });
  const navigate = useNavigate();
  const [showBack, setShowBack] = useState(false);
  
  // --- 1.1 STATE MANAGEMENT ---
  // Keep deterministic defaults for stable loading and tests.
  const [week, setWeek] = useState(1);
  const [games, setGames] = useState([]);
  const [showProjected, setShowProjected] = useState(true);
  const [showScoreInfo, setShowScoreInfo] = useState(false);

  const syncQueryParams = (nextWeek, projectedState) => {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    url.searchParams.set('week', String(nextWeek));
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

  // 1.1.1 Initialize as true to handle the initial mount without a sync setState
  const [loading, setLoading] = useState(true);

  // --- 1.1.2 Fetch User/League Info ---
  useEffect(() => {
    // show back button if history has previous entry
    if (window.history.length > 1) setShowBack(true);

    async function fetchUserLeague() {
      try {
        const userRes = await apiClient.get('/auth/me');
        let leagueName = '';
        if (userRes.data.league_id) {
          const leagueRes = await apiClient.get(
            `/leagues/${userRes.data.league_id}`
          );
          leagueName = leagueRes.data.name;
        }
        setUserInfo({ username: userRes.data.username, leagueName });
      } catch {
        setUserInfo({ username: '', leagueName: '' });
      }
    }
    fetchUserLeague();
  }, []);
  // MERGED: One stable function to rule them all
  const fetchMatchups = useCallback(async () => {
    // Note: We don't call setLoading(true) here anymore because the state
    // is initialized as true or set during week-change transitions.
    try {
      const res = await apiClient.get(`/matchups/week/${week}`);
      // some backends may wrap or return object; ensure we always store an array
      setGames(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Matchup feed failed:', err);
    } finally {
      setLoading(false);
    }
  }, [week]);

  useEffect(() => {
    fetchMatchups();
  }, [fetchMatchups]);

  // --- 1.3 UTILITIES ---
  const handleWeekChange = (newWeek) => {
    if (newWeek >= 1 && newWeek <= 17 && newWeek !== week) {
      setLoading(true);
      setWeek(newWeek);
      syncQueryParams(newWeek, showProjected);
    }
  };
  
  const handleToggleChange = () => {
    const newState = !showProjected;
    setShowProjected(newState);
    syncQueryParams(week, newState);
  };

  const getScore = (game, side) => {
    if (showProjected) {
      return side === 'home' ? game.home_projected : game.away_projected;
    }
    return side === 'home' ? game.home_score : game.away_score;
  };

  // --- 2.1 RENDER LOGIC (The View) ---
  return (
    <div className={`${pageShell} pb-20 animate-fade-in`}>
      {/* HEADER + USER/LEAGUE CONTEXT */}
      <div className={`${pageHeader} flex items-start justify-between`}>
        <div>
          <h1 className={pageTitle}>Matchups</h1>
          <p className={pageSubtitle}>
            Weekly head-to-head scoreboard and matchup detail access.
          </p>
        </div>
        {showBack && (
          <button
            className={`${buttonSecondary} w-fit px-3 py-1.5 text-xs`}
            onClick={() => navigate(-1)}
          >
            ← Back
          </button>
        )}
      </div>

      <div
        className={`${cardSurface} flex flex-col md:flex-row justify-between items-center`}
      >
        <div className="text-lg font-semibold text-slate-900 dark:text-white">
          User:{' '}
          <span className="text-cyan-600 dark:text-cyan-400">
            {userInfo.username || '...'}
          </span>
        </div>
        <div className="text-lg font-semibold text-slate-900 dark:text-white">
          League:{' '}
          <span className="text-cyan-600 dark:text-cyan-400">
            {userInfo.leagueName || '...'}
          </span>
        </div>
      </div>
      {/* 2.2 WEEK SELECTOR & HEADER */}
      <div className={cardSurface}>
        <div className="flex justify-between items-center mb-4">
          <button
            onClick={() => handleWeekChange(week - 1)}
            disabled={week === 1}
            aria-label="Previous week"
            className="p-2 bg-slate-800 rounded-full hover:bg-slate-700 disabled:opacity-30 transition"
          >
            <FiChevronLeft size={24} className="text-white" />
          </button>

          <div className="text-center">
            <div className="flex items-center justify-center gap-3">
              <h1 className="flex items-center justify-center gap-2 text-3xl font-black tracking-tight text-slate-900 dark:text-white">
                <FiCalendar className="text-yellow-500" />
                Week
              </h1>
              {/* Week Dropdown */}
              <select
                value={week}
                onChange={(e) => handleWeekChange(parseInt(e.target.value))}
                className="bg-slate-800 text-white font-black text-2xl rounded-lg px-3 py-1 border border-slate-700 hover:border-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 transition"
              >
                {Array.from({ length: 17 }, (_, i) => i + 1).map((w) => (
                  <option key={w} value={w}>
                    {w}
                  </option>
                ))}
              </select>
            </div>
            {games.length > 0 && (
              <div className="flex flex-col items-center mt-2">
                <span
                  className={`text-xs font-bold uppercase tracking-widest px-2 py-0.5 rounded ${games[0].label === 'Playoffs' ? 'bg-orange-500/20 text-orange-400' : 'text-slate-500'}`}
                >
                  {games[0].label}
                </span>
                <span className="text-[10px] text-slate-400 font-mono mt-1">
                  {games[0].date_range}
                </span>
              </div>
            )}
          </div>

          <button
            onClick={() => handleWeekChange(week + 1)}
            disabled={week === 17}
            aria-label="Next week"
            className="p-2 bg-slate-800 rounded-full hover:bg-slate-700 disabled:opacity-30 transition"
          >
            <FiChevronRight size={24} className="text-white" />
          </button>
        </div>

        <div className="flex justify-center border-t border-slate-800 pt-4">
          <div className="relative flex items-center gap-2">
            <button
              onClick={handleToggleChange}
              aria-label="Toggle projected scores"
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-slate-950 border border-slate-700 hover:border-slate-500 transition"
            >
              <span
                className={`text-xs font-bold uppercase ${!showProjected ? 'text-white' : 'text-slate-500'}`}
              >
                Actual
              </span>
              {showProjected ? (
                <FiToggleRight size={24} className="text-blue-400" />
              ) : (
                <FiToggleLeft size={24} className="text-slate-500" />
              )}
              <span
                className={`text-xs font-bold uppercase ${showProjected ? 'text-blue-400' : 'text-slate-500'}`}
              >
                Projected
              </span>
            </button>

            <div
              className="relative"
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
                <div className="absolute right-0 mt-2 w-72 rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs text-slate-300 shadow-xl z-20">
                  {showProjected
                    ? 'Projected shows the expected team total based on current starters and league scoring rules.'
                    : 'Actual shows the current recorded matchup total from live/completed scoring updates.'}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 2.3 MATCHUP GRID */}
      {loading ? (
        // Skeleton Loading
        <div>
          <div className="mb-4 text-sm font-bold text-slate-500">Loading Week {week}</div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl animate-pulse"
              >
                <div className="p-6 flex justify-between items-center">
                  <div className="text-center w-1/3">
                    <div className="w-12 h-12 mx-auto bg-slate-800 rounded-full mb-2"></div>
                    <div className="h-4 bg-slate-800 rounded w-20 mx-auto mb-1"></div>
                    <div className="h-6 bg-slate-700 rounded w-12 mx-auto"></div>
                  </div>
                  <div className="text-center w-1/3">
                    <div className="h-6 bg-slate-800 rounded w-8 mx-auto"></div>
                  </div>
                  <div className="text-center w-1/3">
                    <div className="w-12 h-12 mx-auto bg-slate-800 rounded-full mb-2"></div>
                    <div className="h-4 bg-slate-800 rounded w-20 mx-auto mb-1"></div>
                    <div className="h-6 bg-slate-700 rounded w-12 mx-auto"></div>
                  </div>
                </div>
                <div className="h-12 bg-slate-950/30 border-t border-slate-800"></div>
              </div>
            ))}
          </div>
        </div>
      ) : games.length === 0 ? (
        // Empty State
        <div className="text-center py-20">
          <FiInbox className="mx-auto text-6xl text-slate-700 mb-4" />
          <h3 className="text-xl font-bold text-slate-400 mb-2">
            No matchups scheduled for Week {week}
          </h3>
          <p className="text-sm text-slate-500">
            Check back later or navigate to a different week.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {games.map((game) => (
            <div
              key={game.id}
              className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden hover:border-slate-600 transition shadow-xl group flex flex-col relative"
            >
              {/* Game Status Badge */}
              {game.game_status && (
                <div className="absolute top-2 right-2 z-10">
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                      game.game_status === 'FINAL'
                        ? 'bg-green-900/30 text-green-400 border border-green-900/50'
                        : game.game_status === 'IN_PROGRESS'
                          ? 'bg-red-900/30 text-red-400 border border-red-900/50 animate-pulse'
                          : 'bg-slate-800 text-slate-500 border border-slate-700'
                    }`}
                  >
                    {game.game_status === 'NOT_STARTED' ? 'Upcoming' : game.game_status.replace('_', ' ')}
                  </span>
                </div>
              )}
              
              <div className="p-6 flex justify-between items-center relative flex-grow">
                {/* Home */}
                <div className="text-center w-1/3">
                  <div className="mx-auto mb-2 flex justify-center">
                    <TeamLogo teamInfo={game.home_team_info} size="md" />
                  </div>
                  <div className="font-bold text-white text-sm truncate">
                    {game.home_team_info?.team_name || game.home_team}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 mt-1">
                    {game.home_team_info?.division_name || 'No Division'}
                  </div>
                  <div
                    className={`font-mono text-2xl font-bold mt-1 ${showProjected ? 'text-blue-400' : 'text-white'}`}
                  >
                    {getScore(game, 'home')}
                  </div>
                </div>

                <div className="text-center w-1/3 flex flex-col items-center">
                  <div className="text-slate-600 font-black italic text-xl opacity-20">
                    VS
                  </div>
                  {showProjected && (
                    <span className="text-[10px] text-blue-500/50 uppercase font-bold mt-1">
                      Proj
                    </span>
                  )}
                </div>

                {/* Away */}
                <div className="text-center w-1/3">
                  <div className="mx-auto mb-2 flex justify-center">
                    <TeamLogo teamInfo={game.away_team_info} size="md" />
                  </div>
                  <div className="font-bold text-white text-sm truncate">
                    {game.away_team_info?.team_name || game.away_team}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 mt-1">
                    {game.away_team_info?.division_name || 'No Division'}
                  </div>
                  <div
                    className={`font-mono text-2xl font-bold mt-1 ${showProjected ? 'text-blue-400' : 'text-white'}`}
                  >
                    {getScore(game, 'away')}
                  </div>
                </div>
              </div>

              {(game.division_context?.is_division_matchup || game.rivalry_context?.is_rivalry_week) && (
                <div className="px-4 pb-3 -mt-1 flex flex-wrap items-center justify-center gap-2">
                  {game.division_context?.is_division_matchup && (
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded border border-cyan-700 bg-cyan-900/20 text-cyan-300">
                      Division Matchup
                    </span>
                  )}
                  {game.rivalry_context?.is_rivalry_week && (
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded border border-rose-700 bg-rose-900/20 text-rose-300">
                      Rivalry: {game.rivalry_context?.rivalry_name || 'Featured'}
                    </span>
                  )}
                </div>
              )}

              <Link
                to={`/matchup/${game.id}`}
                className="block p-3 bg-slate-950/30 border-t border-slate-800 text-center hover:bg-slate-800 transition"
              >
                <div className="text-xs font-bold text-blue-400 uppercase tracking-wider flex items-center justify-center gap-1 mx-auto">
                  <FiActivity /> Game Center
                </div>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
