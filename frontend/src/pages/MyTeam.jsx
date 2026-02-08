import { useEffect, useState, useMemo } from 'react'
import axios from 'axios'
import { 
  FiShield, FiDollarSign, FiUser, FiAlertTriangle, 
  FiCheckCircle, FiXCircle, FiSearch, FiFilter 
} from 'react-icons/fi'

export default function MyTeam({ token, activeOwnerId }) {
  const [teamData, setTeamData] = useState(null)
  const [rosterState, setRosterState] = useState([]) 
  const [loading, setLoading] = useState(true)
  const [validationError, setValidationError] = useState(null)
  const [submitSuccess, setSubmitSuccess] = useState(false)
  
  // Sorting, Searching, Filtering
  const [searchTerm, setSearchTerm] = useState('')
  const [sortConfig, setSortConfig] = useState({ key: 'proj_score', direction: 'desc' }) // Default: High Proj first
  const [activeFilter, setActiveFilter] = useState('ALL') // NEW: Position Filter

  const POS_RANK = { QB: 1, RB: 2, WR: 3, TE: 4, DEF: 5, K: 6 }

  // Fetch Data
  useEffect(() => {
    if (token && activeOwnerId) {
      setLoading(true)
      axios.get(`http://127.0.0.1:8000/team/${activeOwnerId}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      .then(res => {
        setTeamData(res.data)
        const processedRoster = res.data.roster.map(p => ({
          ...p,
          status: p.status || 'BENCH',
          position_rank: POS_RANK[p.position] || 99
        }))
        setRosterState(processedRoster)
        setLoading(false)
      })
      .catch(err => { console.error(err); setLoading(false) })
    }
  }, [token, activeOwnerId])

  // --- ACTIONS ---
  const handleStatusChange = (playerId, newStatus) => {
    setRosterState(prev => prev.map(p => 
      p.player_id === playerId ? { ...p, status: newStatus } : p
    ))
    setValidationError(null)
    setSubmitSuccess(false)
  }

  const handleSort = (key) => {
    let direction = 'asc'
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc'
    }
    setSortConfig({ key, direction })
  }

  // --- DERIVED STATE ---
  const processedPlayers = useMemo(() => {
    let players = [...rosterState]

    // 1. Position Filter
    if (activeFilter !== 'ALL') {
      players = players.filter(p => p.position === activeFilter)
    }

    // 2. Search Filter
    if (searchTerm) {
      players = players.filter(p => p.name.toLowerCase().includes(searchTerm.toLowerCase()))
    }

    // 3. Sorting
    players.sort((a, b) => {
      if (a[sortConfig.key] < b[sortConfig.key]) return sortConfig.direction === 'asc' ? -1 : 1
      if (a[sortConfig.key] > b[sortConfig.key]) return sortConfig.direction === 'asc' ? 1 : -1
      return 0
    })

    return players
  }, [rosterState, searchTerm, sortConfig, activeFilter])

  // Split into buckets
  const starters = processedPlayers.filter(p => p.status === 'STARTER')
  const bench = processedPlayers.filter(p => p.status === 'BENCH')
  const taxi = processedPlayers.filter(p => p.status === 'TAXI')

  // --- LIVE TOTALS CALCULATION ---
  const activeStarters = rosterState.filter(p => p.status === 'STARTER') // Use full rosterState for totals, not filtered view
  const totalYTD = activeStarters.reduce((sum, p) => sum + (p.ytd_score || 0), 0).toFixed(2)
  const totalProj = activeStarters.reduce((sum, p) => sum + (p.proj_score || 0), 0).toFixed(2)

  // --- VALIDATION ---
  const starterCount = activeStarters.length
  
  const validateRoster = () => {
    if (starterCount !== 11) return `Incorrect roster size: ${starterCount}/11 active players.`
    
    const counts = { QB: 0, RB: 0, WR: 0, TE: 0, DEF: 0, K: 0 }
    activeStarters.forEach(p => { if (counts[p.position] !== undefined) counts[p.position]++ })

    if (counts.QB < 1 || counts.QB > 2) return `Invalid QB count (${counts.QB}). Must be 1-2.`
    if (counts.RB < 1 || counts.RB > 5) return `Invalid RB count (${counts.RB}). Must be 1-5.`
    if (counts.WR < 1 || counts.WR > 5) return `Invalid WR count (${counts.WR}). Must be 1-5.`
    if (counts.TE < 1 || counts.TE > 2) return `Invalid TE count (${counts.TE}). Must be 1-2.`
    if (counts.DEF < 1 || counts.DEF > 2) return `Invalid DEF count (${counts.DEF}). Must be 1-2.`
    
    const byeConflicts = activeStarters.filter(p => p.bye_week === 8)
    if (byeConflicts.length > 0) {
      if (!window.confirm(`⚠️ WARNING: ${byeConflicts.length} starter(s) are on Bye! Submit?`)) return "Cancelled."
    }
    return null
  }

  const handleSubmit = () => {
    const error = validateRoster()
    if (error) {
      setValidationError(error)
      return
    }
    setValidationError(null)
    setSubmitSuccess(true)
  }

  // --- REUSABLE COMPONENTS ---
  const FilterButton = ({ label }) => (
    <button 
      onClick={() => setActiveFilter(label)}
      className={`px-3 py-1 rounded text-xs font-bold transition-all ${
        activeFilter === label 
          ? 'bg-yellow-500 text-black shadow-lg scale-105' 
          : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white'
      }`}
    >
      {label}
    </button>
  )

  const RosterTable = ({ title, players, titleColor, emptyMsg }) => (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl mb-8 animate-fade-in-up">
      {/* Table Header */}
      <div className={`p-4 border-b border-slate-800 flex justify-between items-center ${titleColor} bg-slate-950/50`}>
        <h3 className="font-bold uppercase tracking-wider flex items-center gap-2">
          {title} <span className="text-xs opacity-60 bg-black/30 px-2 py-1 rounded">{players.length}</span>
        </h3>
        
        {/* LIVE TOTALS (Only show for Starters) */}
        {title === "Active Lineup" && (
           <div className="flex gap-4 text-xs font-mono">
             <div className="text-right">
               <div className="text-slate-500 uppercase">Total YTD</div>
               <div className="font-bold text-white">{totalYTD}</div>
             </div>
             <div className="text-right">
               <div className="text-slate-500 uppercase">Total Proj</div>
               <div className="font-bold text-blue-400">{totalProj}</div>
             </div>
           </div>
        )}
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-400">
          <thead className="bg-slate-950 text-xs uppercase font-bold text-slate-500 border-b border-slate-800 cursor-pointer select-none">
            <tr>
              <th className="px-6 py-3 hover:text-white transition" onClick={() => handleSort('position_rank')}>Pos {sortConfig.key==='position_rank' && (sortConfig.direction==='asc' ? '↓' : '↑')}</th>
              <th className="px-6 py-3 hover:text-white transition" onClick={() => handleSort('name')}>Player {sortConfig.key==='name' && (sortConfig.direction==='asc' ? '↓' : '↑')}</th>
              <th className="px-6 py-3 hover:text-white transition" onClick={() => handleSort('bye_week')}>Bye {sortConfig.key==='bye_week' && (sortConfig.direction==='asc' ? '↓' : '↑')}</th>
              <th className="px-6 py-3 text-right hover:text-white transition" onClick={() => handleSort('ytd_score')}>YTD {sortConfig.key==='ytd_score' && (sortConfig.direction==='asc' ? '↓' : '↑')}</th>
              <th className="px-6 py-3 text-right hover:text-white transition" onClick={() => handleSort('proj_score')}>Proj {sortConfig.key==='proj_score' && (sortConfig.direction==='asc' ? '↓' : '↑')}</th>
              <th className="px-6 py-3 text-center">Move To</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {players.map((p) => (
              <tr key={p.player_id} className="hover:bg-slate-800/50 transition duration-150">
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 rounded text-xs font-bold border ${
                    p.position === 'QB' ? 'text-red-300 border-red-900 bg-red-900/20' :
                    p.position === 'RB' ? 'text-green-300 border-green-900 bg-green-900/20' :
                    p.position === 'WR' ? 'text-blue-300 border-blue-900 bg-blue-900/20' :
                    p.position === 'TE' ? 'text-orange-300 border-orange-900 bg-orange-900/20' :
                    'text-slate-300 border-slate-600'
                  }`}>{p.position}</span>
                </td>
                <td className="px-6 py-4 font-bold text-white">
                  {p.name}
                  <div className="text-[10px] font-normal text-slate-500">{p.nfl_team}</div>
                </td>
                <td className="px-6 py-4">
                  {p.bye_week === 8 ? <span className="text-red-500 font-bold flex gap-1 items-center"><FiAlertTriangle/> W8</span> : `Week ${p.bye_week}`}
                </td>
                <td className="px-6 py-4 text-right font-mono">{p.ytd_score}</td>
                <td className="px-6 py-4 text-right font-mono text-blue-400 font-bold">{p.proj_score}</td>
                <td className="px-6 py-4 text-center">
                  <select 
                    value={p.status}
                    onChange={(e) => handleStatusChange(p.player_id, e.target.value)}
                    className="bg-slate-800 border border-slate-600 text-slate-300 text-xs rounded px-2 py-1 outline-none focus:border-yellow-500 transition-colors hover:border-slate-500"
                  >
                    <option value="STARTER">Starter</option>
                    <option value="BENCH">Bench</option>
                    <option value="TAXI">Taxi Squad</option>
                  </select>
                </td>
              </tr>
            ))}
            {players.length === 0 && (
              <tr><td colSpan="6" className="text-center py-8 text-slate-600 italic">{emptyMsg}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )

  if (loading) return <div className="p-8 text-white animate-pulse">Loading Roster...</div>
  if (!teamData) return <div className="text-red-500 p-8">Error loading team.</div>

  return (
    <div className="space-y-6 pb-20 animate-fade-in">
      
      {/* 1. HEADER & CONTROLS */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6 shadow-lg">
        <div className="flex flex-col xl:flex-row justify-between items-center gap-6">
          
          {/* Team Info */}
          <div className="flex items-center gap-4 w-full xl:w-auto">
            <div className="p-4 bg-slate-800 rounded-full border border-slate-600 shadow-inner">
               <FiUser size={32} className="text-slate-400" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-white italic tracking-tighter uppercase">{teamData.team_name}</h1>
              <div className="flex items-center gap-2 mt-1">
                 <div className={`px-2 py-0.5 rounded text-[10px] font-bold border flex items-center gap-1 ${starterCount === 11 ? 'text-green-400 border-green-500/50 bg-green-900/20' : 'text-red-400 border-red-500/50 bg-red-900/20'}`}>
                   {starterCount === 11 ? <FiCheckCircle /> : <FiAlertTriangle />}
                   {starterCount}/11 STARTERS
                 </div>
                 <span className="text-xs text-slate-500">Week 8 Matchup</span>
              </div>
            </div>
          </div>

          {/* Filters & Search */}
          <div className="flex flex-col md:flex-row gap-4 items-center w-full xl:w-auto">
             {/* Position Filters */}
             <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800">
               {['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DEF'].map(pos => (
                 <FilterButton key={pos} label={pos} />
               ))}
             </div>

             {/* Search Bar */}
             <div className="relative w-full md:w-48">
                <FiSearch className="absolute left-3 top-2.5 text-slate-500" />
                <input 
                  type="text" 
                  placeholder="Find player..." 
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg py-2 pl-9 pr-4 text-xs text-white focus:border-yellow-500 outline-none transition-colors"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
             </div>
          </div>

          {/* Submit Button */}
          <div className="flex items-center gap-4 w-full xl:w-auto justify-end">
             <div className="text-right hidden xl:block">
               <div className="text-[10px] text-slate-500 uppercase font-bold">Waiver Cap</div>
               <div className="text-green-400 font-mono font-bold">${teamData.remaining_budget}</div>
             </div>
             <button 
                onClick={handleSubmit}
                className={`px-6 py-3 rounded-lg font-bold shadow-lg flex items-center gap-2 transition-all active:scale-95 ${
                  submitSuccess ? 'bg-green-600 text-white ring-2 ring-green-400' : 'bg-blue-600 hover:bg-blue-500 text-white'
                }`}
              >
                {submitSuccess ? 'ROSTER SAVED' : 'SUBMIT LINEUP'}
             </button>
          </div>
        </div>
      </div>

      {/* 2. ERROR MESSAGE */}
      {validationError && (
        <div className="bg-red-900/20 border border-red-500/50 p-4 rounded-xl flex items-center gap-3 text-red-200 animate-pulse">
          <FiXCircle size={24} className="text-red-500" />
          <span className="font-bold">{validationError}</span>
        </div>
      )}

      {/* 3. ROSTER BUCKETS */}
      <RosterTable 
        title="Active Lineup" 
        players={starters} 
        titleColor="text-green-400" 
        emptyMsg="Your starting lineup is empty." 
      />
      
      <RosterTable 
        title="Bench" 
        players={bench} 
        titleColor="text-yellow-400" 
        emptyMsg="Bench is empty." 
      />
      
      <RosterTable 
        title="Taxi Squad" 
        players={taxi} 
        titleColor="text-red-400" 
        emptyMsg="Taxi squad is empty." 
      />

    </div>
  )
}