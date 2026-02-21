// frontend/src/pages/Matchups.jsx
import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  FiChevronLeft,
  FiChevronRight,
  FiCalendar,
  FiActivity,
  FiToggleRight,
  FiToggleLeft,
  FiInfo,
} from 'react-icons/fi';

// Professional Imports
import apiClient from '@api/client';

export default function Matchups() {
  // --- USER/LEAGUE CONTEXT ---
  const [userInfo, setUserInfo] = useState({ username: '', leagueName: '' });
  // --- 1.1 STATE MANAGEMENT ---
  const [week, setWeek] = useState(1);
  const [games, setGames] = useState([]);
  const [showProjected, setShowProjected] = useState(true);
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

  // 1.1.1 Initialize as true to handle the initial mount without a sync setState
  const [loading, setLoading] = useState(true);

  // --- 1.1.2 Fetch User/League Info ---
  useEffect(() => {
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
      } catch (err) {
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
      setGames(res.data);
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
  const handleWeekChange = (direction) => {
    if (direction === 'prev' && week > 1) {
      setLoading(true); // Trigger loading spinner for the new week
      setWeek(week - 1);
    }
    if (direction === 'next' && week < 17) {
      setLoading(true);
      setWeek(week + 1);
    }
  };

  const getScore = (game, side) => {
    if (showProjected) {
      return side === 'home' ? game.home_projected : game.away_projected;
    }
    return side === 'home' ? game.home_score : game.away_score;
  };

  // --- 2.1 RENDER LOGIC (The View) ---
  return (
    <div className="space-y-6 pb-20 animate-fade-in">
      {/* USER/LEAGUE CONTEXT */}
      <div className="flex flex-col md:flex-row justify-between items-center bg-slate-900 border border-slate-800 rounded-xl p-4 mb-4">
        <div className="text-lg font-bold text-white">
          User:{' '}
          <span className="text-yellow-400">{userInfo.username || '...'}</span>
        </div>
        <div className="text-lg font-bold text-white">
          League:{' '}
          <span className="text-blue-400">{userInfo.leagueName || '...'}</span>
        </div>
      </div>
      {/* 2.2 WEEK SELECTOR & HEADER */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-4 shadow-lg">
        <div className="flex justify-between items-center mb-4">
          <button
            onClick={() => handleWeekChange('prev')}
            disabled={week === 1}
            aria-label="Previous week"
            className="p-2 bg-slate-800 rounded-full hover:bg-slate-700 disabled:opacity-30 transition"
          >
            <FiChevronLeft size={24} className="text-white" />
          </button>

          <div className="text-center">
            <h1 className="text-3xl font-black text-white italic tracking-tighter uppercase flex items-center gap-2 justify-center">
              <FiCalendar className="text-yellow-500" />
              Week {week}
            </h1>
            {games.length > 0 && (
              <div className="flex flex-col items-center">
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
            onClick={() => handleWeekChange('next')}
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
              onClick={() => setShowProjected(!showProjected)}
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
        <div className="text-center py-12 text-slate-500 animate-pulse font-black uppercase tracking-widest">
          Loading Week {week}...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {games.map((game) => (
            <div
              key={game.id}
              className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden hover:border-slate-600 transition shadow-xl group flex flex-col"
            >
              <div className="p-6 flex justify-between items-center relative flex-grow">
                {/* Home */}
                <div className="text-center w-1/3">
                  <div className="w-12 h-12 mx-auto bg-slate-800 rounded-full flex items-center justify-center font-bold text-slate-400 mb-2 border border-slate-700 group-hover:border-blue-500 transition">
                    {game.home_team[0]}
                  </div>
                  <div className="font-bold text-white text-sm truncate">
                    {game.home_team}
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
                  <div className="w-12 h-12 mx-auto bg-slate-800 rounded-full flex items-center justify-center font-bold text-slate-400 mb-2 border border-slate-700 group-hover:border-red-500 transition">
                    {game.away_team[0]}
                  </div>
                  <div className="font-bold text-white text-sm truncate">
                    {game.away_team}
                  </div>
                  <div
                    className={`font-mono text-2xl font-bold mt-1 ${showProjected ? 'text-blue-400' : 'text-white'}`}
                  >
                    {getScore(game, 'away')}
                  </div>
                </div>
              </div>

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
