// frontend/src/pages/Matchups.jsx
import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { FiChevronLeft, FiChevronRight, FiCalendar, FiActivity, FiToggleRight, FiToggleLeft } from 'react-icons/fi'

// Professional Imports
import apiClient from '@api/client'

export default function Matchups() {
  // --- 1.1 STATE MANAGEMENT ---
  const [week, setWeek] = useState(1)
  const [games, setGames] = useState([])
  const [showProjected, setShowProjected] = useState(true)
  
  // 1.1.1 Start as true to avoid sync setState in useEffect
  const [loading, setLoading] = useState(true)

  // --- 1.2 DATA RETRIEVAL (The Engine) ---
  const fetchMatchups = useCallback(() => {
    setLoading(true)
    apiClient.get(`/matchups/week/${week}`)
      .then(res => {
        setGames(res.data)
      })
      .catch(err => {
        console.error("Matchup feed failed:", err)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [week])

  useEffect(() => {
    fetchMatchups()
  }, [fetchMatchups])

  // --- 1.3 UTILITIES ---
  const handleWeekChange = (direction) => {
    if (direction === 'prev' && week > 1) setWeek(week - 1)
    if (direction === 'next' && week < 17) setWeek(week + 1)
  }

  const getScore = (game, side) => {
    if (showProjected) {
      return side === 'home' ? game.home_projected : game.away_projected
    }
    return side === 'home' ? game.home_score : game.away_score
  }

  // --- 2.1 RENDER LOGIC (The View) ---

  return (
    <div className="space-y-6 pb-20 animate-fade-in">
      
      {/* 2.2 WEEK SELECTOR & HEADER */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-4 shadow-lg">
          <div className="flex justify-between items-center mb-4">
              <button 
                onClick={() => handleWeekChange('prev')} 
                disabled={week === 1} 
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
                    <span className={`text-xs font-bold uppercase tracking-widest px-2 py-0.5 rounded ${games[0].label === 'Playoffs' ? 'bg-orange-500/20 text-orange-400' : 'text-slate-500'}`}>
                        {games[0].label}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono mt-1">{games[0].date_range}</span>
                  </div>
                )}
              </div>

              <button 
                onClick={() => handleWeekChange('next')} 
                disabled={week === 17} 
                className="p-2 bg-slate-800 rounded-full hover:bg-slate-700 disabled:opacity-30 transition"
              >
                <FiChevronRight size={24} className="text-white" />
              </button>
          </div>

          {/* 2.3 TOGGLE BAR */}
          <div className="flex justify-center border-t border-slate-800 pt-4">
            <button 
                onClick={() => setShowProjected(!showProjected)}
                className="flex items-center gap-2 px-4 py-2 rounded-full bg-slate-950 border border-slate-700 hover:border-slate-500 transition"
            >
                <span className={`text-xs font-bold uppercase ${!showProjected ? 'text-white' : 'text-slate-500'}`}>Actual</span>
                {showProjected ? <FiToggleRight size={24} className="text-blue-400" /> : <FiToggleLeft size={24} className="text-slate-500" />}
                <span className={`text-xs font-bold uppercase ${showProjected ? 'text-blue-400' : 'text-slate-500'}`}>Projected</span>
            </button>
          </div>
      </div>

      {/* 2.4 MATCHUP GRID */}
      {loading ? (
        <div className="text-center py-12 text-slate-500 animate-pulse font-black uppercase tracking-widest">
          Loading Week {week}...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {games.map((game) => (
            <div key={game.id} className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden hover:border-slate-600 transition shadow-xl group flex flex-col">
              
              <div className="p-6 flex justify-between items-center relative flex-grow">
                {/* Home */}
                <div className="text-center w-1/3">
                  <div className="w-12 h-12 mx-auto bg-slate-800 rounded-full flex items-center justify-center font-bold text-slate-400 mb-2 border border-slate-700 group-hover:border-blue-500 transition">
                    {game.home_team[0]}
                  </div>
                  <div className="font-bold text-white text-sm truncate">{game.home_team}</div>
                  <div className={`font-mono text-2xl font-bold mt-1 ${showProjected ? 'text-blue-400' : 'text-white'}`}>
                      {getScore(game, 'home')}
                  </div>
                </div>

                <div className="text-center w-1/3 flex flex-col items-center">
                  <div className="text-slate-600 font-black italic text-xl opacity-20">VS</div>
                  {showProjected && <span className="text-[10px] text-blue-500/50 uppercase font-bold mt-1">Proj</span>}
                </div>

                {/* Away */}
                <div className="text-center w-1/3">
                  <div className="w-12 h-12 mx-auto bg-slate-800 rounded-full flex items-center justify-center font-bold text-slate-400 mb-2 border border-slate-700 group-hover:border-red-500 transition">
                    {game.away_team[0]}
                  </div>
                  <div className="font-bold text-white text-sm truncate">{game.away_team}</div>
                  <div className={`font-mono text-2xl font-bold mt-1 ${showProjected ? 'text-blue-400' : 'text-white'}`}>
                      {getScore(game, 'away')}
                  </div>
                </div>
              </div>

              {/* ACTION LINK */}
              <Link to={`/matchup/${game.id}`} className="block p-3 bg-slate-950/30 border-t border-slate-800 text-center hover:bg-slate-800 transition">
                  <div className="text-xs font-bold text-blue-400 uppercase tracking-wider flex items-center justify-center gap-1 mx-auto">
                    <FiActivity /> Game Center
                  </div>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}