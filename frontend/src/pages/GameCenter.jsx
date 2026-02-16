import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import axios from 'axios'
import { FiArrowLeft } from 'react-icons/fi'

// 1.1 COMPONENT DECLARED OUTSIDE (Fixes "Cannot create components during render")
// This ensures React doesn't re-create the component definition on every state change.
const RosterColumn = ({ players, teamName, colorClass }) => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
    <div className="bg-slate-950/50 p-3 border-b border-slate-800 text-center">
      <h3 className="font-bold text-slate-400 uppercase tracking-widest text-xs">{teamName} Starters</h3>
    </div>
    <div className="divide-y divide-slate-800">
      {players.length === 0 ? (
        <div className="p-8 text-center text-slate-600 italic text-sm">No starters set.</div>
      ) : (
        players.map(p => (
          <div key={p.player_id} className="flex justify-between items-center p-3 hover:bg-slate-800/30 transition">
            <div className="flex items-center gap-3">
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded w-8 text-center ${
                p.position === 'QB' ? 'bg-red-900/20 text-red-400 border border-red-900/50' :
                p.position === 'RB' ? 'bg-green-900/20 text-green-400 border border-green-900/50' :
                p.position === 'WR' ? 'bg-blue-900/20 text-blue-400 border border-blue-900/50' :
                'bg-slate-800 text-slate-400 border border-slate-700'
              }`}>
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
)

export default function GameCenter({ token }) {
  const { id } = useParams()
  const [game, setGame] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (token && id) {
      axios.get(`http://127.0.0.1:8000/matchups/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      .then(res => {
        setGame(res.data)
        setLoading(false)
      })
      .catch(err => { 
        console.error(err)
        setLoading(false) 
      })
    }
  }, [token, id])

  if (loading || !game) {
    return (
      <div className="text-center py-20 text-slate-500 animate-pulse">
        Loading Game Center...
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-20 animate-fade-in">
      
      {/* HEADER */}
      <div className="flex items-center gap-4">
        <Link to="/matchups" className="p-2 bg-slate-800 rounded-full text-slate-400 hover:text-white hover:bg-slate-700 transition">
           <FiArrowLeft size={20} />
        </Link>
        <h1 className="text-xl font-bold text-slate-300 uppercase tracking-wide">
          Week {game.week} Matchup
        </h1>
      </div>

      {/* SCOREBOARD BANNER */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-2xl flex justify-between items-center relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 via-transparent to-red-600 opacity-50"></div>
        
        {/* Home */}
        <div className="text-center z-10 w-1/3">
           <h2 className="text-xl md:text-3xl font-black text-white italic tracking-tighter uppercase mb-2 truncate">{game.home_team}</h2>
           <div className="text-4xl md:text-6xl font-mono font-bold text-blue-400">{game.home_projected.toFixed(2)}</div>
           <div className="text-xs text-blue-500/50 uppercase font-bold mt-1">Projected</div>
        </div>

        {/* VS */}
        <div className="text-center z-10">
           <div className="w-10 h-10 md:w-16 md:h-16 bg-slate-800 rounded-full flex items-center justify-center text-slate-500 font-black italic border border-slate-700 shadow-inner text-sm md:text-xl">VS</div>
        </div>

        {/* Away */}
        <div className="text-center z-10 w-1/3">
           <h2 className="text-xl md:text-3xl font-black text-white italic tracking-tighter uppercase mb-2 truncate">{game.away_team}</h2>
           <div className="text-4xl md:text-6xl font-mono font-bold text-red-400">{game.away_projected.toFixed(2)}</div>
           <div className="text-xs text-red-500/50 uppercase font-bold mt-1">Projected</div>
        </div>
      </div>

      {/* ROSTERS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative">
         <div className="hidden md:block absolute left-1/2 top-0 bottom-0 w-px bg-slate-800/50 -translate-x-1/2"></div>
         
         {/* Using our outside-declared component */}
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
  )
}