import { useEffect, useState, useMemo, useCallback } from 'react'
import { FiUser, FiAlertTriangle } from 'react-icons/fi'

// Professional Imports
import apiClient from '@api/client'
import { ChatInterface } from '@components/chat';

// --- 1.1 CONSTANTS & HELPERS (Outside Render) ---
const POS_RANK = { QB: 1, RB: 2, WR: 3, TE: 4, DEF: 5, K: 6 }

const FilterButton = ({ label, activeFilter, setActiveFilter }) => (
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

const RosterTable = ({ title, players, titleColor, emptyMsg, totalYTD, totalProj, sortConfig, handleSort }) => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl mb-8 animate-fade-in-up">
    <div className={`p-4 border-b border-slate-800 flex justify-between items-center ${titleColor} bg-slate-950/50`}>
      <h3 className="font-bold uppercase tracking-wider flex items-center gap-2">
        {title} <span className="text-xs opacity-60 bg-black/30 px-2 py-1 rounded">{players.length}</span>
      </h3>
      
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

export default function MyTeam({ activeOwnerId }) {
  // --- 1.2 STATE MANAGEMENT ---
  const [teamData, setTeamData] = useState(null)
  const [rosterState, setRosterState] = useState([]) 
  // FIX: Start loading as true to avoid sync setState inside useEffect
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortConfig, setSortConfig] = useState({ key: 'proj_score', direction: 'desc' })
  const [activeFilter, setActiveFilter] = useState('ALL')

  // --- 1.3 DATA RETRIEVAL (The Engine) ---
  const fetchTeam = useCallback(() => {
    if (activeOwnerId) {
      // apiClient handles the Base URL and the token automatically via interceptors
      apiClient.get(`/team/${activeOwnerId}`)
        .then(res => {
          setTeamData(res.data)
          const processedRoster = res.data.roster.map(p => ({
            ...p,
            status: p.status || 'BENCH',
            position_rank: POS_RANK[p.position] || 99
          }))
          setRosterState(processedRoster)
        })
        .catch(err => console.error("Roster fetch failed", err))
        .finally(() => setLoading(false))
    }
  }, [activeOwnerId])

  useEffect(() => {
    fetchTeam()
  }, [fetchTeam])

  // --- 1.4 UTILITIES & DERIVED STATE ---
  const handleSort = (key) => {
    let direction = 'asc'
    if (sortConfig.key === key && sortConfig.direction === 'asc') direction = 'desc'
    setSortConfig({ key, direction })
  }

  const processedPlayers = useMemo(() => {
    let players = [...rosterState]
    if (activeFilter !== 'ALL') players = players.filter(p => p.position === activeFilter)
    if (searchTerm) players = players.filter(p => p.name.toLowerCase().includes(searchTerm.toLowerCase()))
    
    players.sort((a, b) => {
      if (a[sortConfig.key] < b[sortConfig.key]) return sortConfig.direction === 'asc' ? -1 : 1
      if (a[sortConfig.key] > b[sortConfig.key]) return sortConfig.direction === 'asc' ? 1 : -1
      return 0
    })
    return players
  }, [rosterState, searchTerm, sortConfig, activeFilter])

  const starters = processedPlayers.filter(p => p.status === 'STARTER')
  const bench = processedPlayers.filter(p => p.status === 'BENCH')

  const totalYTD = starters.reduce((sum, p) => sum + (p.ytd_score || 0), 0).toFixed(2)
  const totalProj = starters.reduce((sum, p) => sum + (p.proj_score || 0), 0).toFixed(2)

  // --- 2.1 RENDER LOGIC (The View) ---

  if (loading) return <div className="p-8 text-white animate-pulse">Loading Roster...</div>
  if (!teamData) return <div className="text-red-500 p-8">Error loading team.</div>

  return (
    <div className="space-y-6 pb-20 animate-fade-in">
       <div className="bg-gradient-to-r from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6 shadow-lg">
        <div className="flex flex-col xl:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-4 w-full xl:w-auto">
            <div className="p-4 bg-slate-800 rounded-full border border-slate-600 shadow-inner">
               <FiUser size={32} className="text-slate-400" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-white italic tracking-tighter uppercase">{teamData.team_name}</h1>
            </div>
          </div>

          <div className="flex flex-col md:flex-row gap-4 items-center w-full xl:w-auto">
             <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800">
               {['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DEF'].map(pos => (
                 <FilterButton key={pos} label={pos} activeFilter={activeFilter} setActiveFilter={setActiveFilter} />
               ))}
             </div>
          </div>
        </div>
      </div>

      <RosterTable 
        title="Active Lineup" 
        players={starters} 
        titleColor="text-green-400" 
        emptyMsg="Your starting lineup is empty."
        totalYTD={totalYTD}
        totalProj={totalProj}
        sortConfig={sortConfig}
        handleSort={handleSort}
      />
      
      <RosterTable 
        title="Bench" 
        players={bench} 
        titleColor="text-yellow-400" 
        emptyMsg="Bench is empty."
        sortConfig={sortConfig}
        handleSort={handleSort}
      />
    </div>
  )
}