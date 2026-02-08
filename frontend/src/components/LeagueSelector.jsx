import { useEffect, useState } from 'react'
import axios from 'axios'

// 1. ADD 'token' to props so we can use it in the API call
export default function LeagueSelector({ onLeagueSelect, token }) {
  const [leagues, setLeagues] = useState([])
  const [newLeagueName, setNewLeagueName] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  
  // 2. ADD 'loading' state definition
  const [loading, setLoading] = useState(true)

  // Fetch available leagues on load
  useEffect(() => {
    if (!token) return; // Don't fetch if no token

    // Correct URL: /league/
    axios.get('http://127.0.0.1:8000/league/', { 
        headers: { Authorization: `Bearer ${token}` } 
    })
    .then(res => {
        setLeagues(res.data)
        setLoading(false)
    })
    .catch(err => {
        console.error("Could not fetch leagues:", err)
        setLoading(false)
    })
  }, [token])

  // Handle Create New League
  const handleCreate = () => {
    if (!newLeagueName) return
    
    // UPDATED URL: Match the backend router prefix '/league/'
    axios.post('http://127.0.0.1:8000/league/', { name: newLeagueName }, {
        headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => {
        setLeagues([...leagues, res.data]) // Add to list immediately
        setNewLeagueName('')
        setIsCreating(false)
      })
      .catch(err => alert("Error creating league. Name might be taken."))
  }

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white">
      <div className="bg-slate-800 p-8 rounded-lg shadow-2xl w-full max-w-md border border-slate-700">
        <h1 className="text-3xl font-black text-center text-yellow-500 mb-2">🏈 FANTASY WAR ROOM</h1>
        <p className="text-slate-400 text-center mb-8">Select your league to enter</p>

        {/* LOADING STATE */}
        {loading ? (
            <div className="text-center text-slate-500 animate-pulse mb-6">Loading Leagues...</div>
        ) : (
            /* LIST OF LEAGUES */
            <div className="space-y-3 mb-6 max-h-60 overflow-y-auto custom-scrollbar">
            {leagues.map(league => (
                <button 
                key={league.id}
                onClick={() => onLeagueSelect(league.id)}
                className="w-full text-left px-4 py-3 bg-slate-700 hover:bg-slate-600 rounded border border-slate-600 hover:border-yellow-500 transition-all flex justify-between group"
                >
                <span className="font-bold">{league.name}</span>
                <span className="text-slate-500 group-hover:text-yellow-400">ENTER →</span>
                </button>
            ))}
            {leagues.length === 0 && <div className="text-center text-slate-500 italic">No leagues found. Create one!</div>}
            </div>
        )}

        {/* CREATE NEW TOGGLE */}
        {!isCreating ? (
          <button 
            onClick={() => setIsCreating(true)}
            className="w-full py-2 text-slate-400 hover:text-white text-sm border-t border-slate-700 pt-4"
          >
            + Create New League
          </button>
        ) : (
          <div className="pt-4 border-t border-slate-700 animate-fade-in">
            <label className="text-xs font-bold text-slate-400 uppercase">New League Name</label>
            <div className="flex gap-2 mt-1">
              <input 
                className="flex-grow bg-slate-900 border border-slate-600 rounded p-2 text-white outline-none focus:border-green-500"
                value={newLeagueName}
                onChange={e => setNewLeagueName(e.target.value)}
                placeholder="e.g. Dynasty 2026"
              />
              <button 
                onClick={handleCreate}
                className="bg-green-600 hover:bg-green-500 px-4 rounded font-bold text-sm"
              >
                SAVE
              </button>
              <button onClick={()=>setIsCreating(false)} className="text-slate-500 hover:text-white px-2">✕</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}