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
import PageTemplate from '@components/layout/PageTemplate';

// Professional Imports
import {
  fetchCurrentUser,
  fetchLeagueById,
} from '@api/commonApi';
import { fetchWeekMatchups } from '@api/matchupsApi';
import { normalizeApiError } from '@api/fetching';
import {
  buttonSecondary,
  cardSurface,
  layerDropdown,
} from '@utils/uiStandards';

export default function Matchups() {
  // --- USER/LEAGUE CONTEXT ---
  const [userInfo, setUserInfo] = useState({ username: '', leagueName: '' });
  const navigate = useNavigate();
  const [showBack, setShowBack] = useState(false);
  
  // --- 1.1 STATE MANAGEMENT ---
  // Initialise from URL query params so navigating back from GameCenter restores context.
  const [week, setWeek] = useState(() => {
    if (typeof window === 'undefined') return 1;
    const p = new URLSearchParams(window.location.search);
    const w = parseInt(p.get('week'), 10);
    return w >= 1 && w <= 17 ? w : 1;
  });
  const [games, setGames] = useState([]);
  const [showProjected, setShowProjected] = useState(() => {
    if (typeof window === 'undefined') return true;
    const p = new URLSearchParams(window.location.search);
    return p.get('view') !== 'actual';
  });
  const [showScoreInfo, setShowScoreInfo] = useState(false);
  const [matchupsError, setMatchupsError] = useState('');

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
        const user = await fetchCurrentUser();
        let leagueName = '';
        if (user?.league_id) {
          const league = await fetchLeagueById(user.league_id);
          leagueName = league?.name || '';
        }
        setUserInfo({ username: user?.username || '', leagueName });
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
      const data = await fetchWeekMatchups(week);
      // some backends may wrap or return object; ensure we always store an array
      setGames(Array.isArray(data) ? data : []);
      setMatchupsError('');
    } catch (err) {
      console.error('Matchup feed failed:', err);
      setMatchupsError(normalizeApiError(err, 'Unable to load matchups right now.'));
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

  const getWinChance = (game, side) => {
    if (side === 'home') {
      return Number(game.home_win_probability ?? 50);
    }
    return Number(game.away_win_probability ?? 50);
  };

  // --- 2.1 RENDER LOGIC (The View) ---
  return (
    <PageTemplate
      hideHeader
      className="pb-20 animate-fade-in"
    >
      {/* Optional back nav; page title is now handled by global Layout header */}
      <div className="mb-4 flex justify-end">
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
            className="rounded-full bg-slate-200 p-2 transition hover:bg-slate-300 disabled:opacity-30 dark:bg-slate-800 dark:hover:bg-slate-700"
          >
            <FiChevronLeft size={24} className="text-slate-700 dark:text-white" />
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
                className="rounded-lg border border-slate-300 bg-white px-3 py-1 text-2xl font-black text-slate-900 transition hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:hover:border-slate-500"
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
            className="rounded-full bg-slate-200 p-2 transition hover:bg-slate-300 disabled:opacity-30 dark:bg-slate-800 dark:hover:bg-slate-700"
          >
            <FiChevronRight size={24} className="text-slate-700 dark:text-white" />
          </button>
        </div>

        <div className="flex justify-center border-t border-slate-200 pt-4 dark:border-slate-800">
          <div className="relative flex items-center gap-2">
            <button
              onClick={handleToggleChange}
              aria-label="Toggle projected scores"
              className="flex items-center gap-2 rounded-full border border-slate-300 bg-white px-4 py-2 transition hover:border-slate-500 dark:border-slate-700 dark:bg-slate-950"
            >
              <span
                className={`text-xs font-bold uppercase ${!showProjected ? 'text-slate-900 dark:text-white' : 'text-slate-500'}`}
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
                className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white text-slate-500 transition hover:border-slate-500 hover:text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400 dark:hover:text-white"
              >
                <FiInfo size={14} />
              </button>

              {showScoreInfo && (
                <div className={`absolute right-0 mt-2 w-72 rounded-lg border border-slate-300 bg-white p-3 text-xs text-slate-700 shadow-xl dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300 ${layerDropdown}`}>
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
      {matchupsError ? (
        <div className="rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300">
          {matchupsError}
        </div>
      ) : null}

      {loading ? (
        // Skeleton Loading
        <div>
          <div className="mb-4 text-sm font-bold text-slate-500">Loading Week {week}</div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl animate-pulse dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="p-6 flex justify-between items-center">
                  <div className="text-center w-1/3">
                    <div className="w-12 h-12 mx-auto rounded-full bg-slate-200 mb-2 dark:bg-slate-800"></div>
                    <div className="h-4 w-20 mx-auto mb-1 rounded bg-slate-200 dark:bg-slate-800"></div>
                    <div className="h-6 w-12 mx-auto rounded bg-slate-300 dark:bg-slate-700"></div>
                  </div>
                  <div className="text-center w-1/3">
                    <div className="h-6 w-8 mx-auto rounded bg-slate-200 dark:bg-slate-800"></div>
                  </div>
                  <div className="text-center w-1/3">
                    <div className="w-12 h-12 mx-auto rounded-full bg-slate-200 mb-2 dark:bg-slate-800"></div>
                    <div className="h-4 w-20 mx-auto mb-1 rounded bg-slate-200 dark:bg-slate-800"></div>
                    <div className="h-6 w-12 mx-auto rounded bg-slate-300 dark:bg-slate-700"></div>
                  </div>
                </div>
                <div className="h-12 border-t border-slate-200 bg-slate-100/70 dark:border-slate-800 dark:bg-slate-950/30"></div>
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
              className="group relative flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl transition hover:border-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-600"
            >
              {/* Game Status Badge */}
              {game.game_status && (
                <div className="absolute top-2 right-2 z-10">
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                      game.game_status === 'FINAL'
                        ? 'border border-green-400/60 bg-green-50 text-green-700 dark:border-green-900/50 dark:bg-green-900/30 dark:text-green-400'
                        : game.game_status === 'IN_PROGRESS'
                          ? 'animate-pulse border border-red-400/60 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-900/30 dark:text-red-400'
                          : 'border border-slate-300 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500'
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
                  <div className="truncate text-sm font-bold text-slate-900 dark:text-white">
                    {game.home_team_info?.team_name || game.home_team}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 mt-1">
                    {game.home_team_info?.division_name || 'No Division'}
                  </div>
                  <div
                    className={`mt-1 font-mono text-2xl font-bold ${showProjected ? 'text-blue-500 dark:text-blue-400' : 'text-slate-900 dark:text-white'}`}
                  >
                    {getScore(game, 'home')}
                  </div>
                </div>

                <div className="text-center w-1/3 flex flex-col items-center">
                  <div className="text-xl font-black italic text-slate-500 opacity-30 dark:text-slate-600 dark:opacity-20">
                    VS
                  </div>
                  {showProjected && (
                    <span className="mt-1 text-[10px] font-bold uppercase text-blue-600/70 dark:text-blue-500/50">
                      Proj
                    </span>
                  )}
                </div>

                {/* Away */}
                <div className="text-center w-1/3">
                  <div className="mx-auto mb-2 flex justify-center">
                    <TeamLogo teamInfo={game.away_team_info} size="md" />
                  </div>
                  <div className="truncate text-sm font-bold text-slate-900 dark:text-white">
                    {game.away_team_info?.team_name || game.away_team}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 mt-1">
                    {game.away_team_info?.division_name || 'No Division'}
                  </div>
                  <div
                    className={`mt-1 font-mono text-2xl font-bold ${showProjected ? 'text-blue-500 dark:text-blue-400' : 'text-slate-900 dark:text-white'}`}
                  >
                    {getScore(game, 'away')}
                  </div>
                </div>
              </div>

              {showProjected && (
                <div className="px-4 pb-4 -mt-1">
                  <div className="mb-1 flex items-center justify-between text-[10px] font-bold uppercase tracking-wider">
                    <span className="text-blue-600 dark:text-blue-300">
                      {getWinChance(game, 'home').toFixed(1)}% Win Chance
                    </span>
                    <span className="text-red-600 dark:text-red-300">
                      {getWinChance(game, 'away').toFixed(1)}% Win Chance
                    </span>
                  </div>
                  <div
                    className="h-2 w-full overflow-hidden rounded-full border border-slate-300 bg-slate-100 dark:border-slate-700 dark:bg-slate-950"
                    role="img"
                    aria-label="Projected matchup win probability"
                  >
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-red-500"
                      style={{ width: `${getWinChance(game, 'home')}%` }}
                    />
                  </div>
                </div>
              )}

              {(game.division_context?.is_division_matchup || game.rivalry_context?.is_rivalry_week) && (
                <div className="px-4 pb-3 -mt-1 flex flex-wrap items-center justify-center gap-2">
                  {game.division_context?.is_division_matchup && (
                    <span className="rounded border border-cyan-500/60 bg-cyan-50 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-cyan-700 dark:border-cyan-700 dark:bg-cyan-900/20 dark:text-cyan-300">
                      Division Matchup
                    </span>
                  )}
                  {game.rivalry_context?.is_rivalry_week && (
                    <span className="rounded border border-rose-500/60 bg-rose-50 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-rose-700 dark:border-rose-700 dark:bg-rose-900/20 dark:text-rose-300">
                      Rivalry: {game.rivalry_context?.rivalry_name || 'Featured'}
                    </span>
                  )}
                </div>
              )}

              <Link
                to={`/matchup/${game.id}?week=${week}&view=${showProjected ? 'projected' : 'actual'}`}
                className="block border-t border-slate-200 bg-slate-50/90 p-3 text-center transition hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-950/30 dark:hover:bg-slate-800"
              >
                <div className="mx-auto flex items-center justify-center gap-1 text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400">
                  <FiActivity /> Game Center
                </div>
              </Link>
            </div>
          ))}
        </div>
      )}
    </PageTemplate>
  );
}
