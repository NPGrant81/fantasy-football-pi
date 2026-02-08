import { useEffect, useState, useRef, useCallback } from 'react'
import axios from 'axios'

// --- CONFIGURATION ---
const ROSTER_SIZE = 14
// Updated to include all positions for the card summary
const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']

// Helper to normalize position names (TD -> DEF)
const normalizePos = (pos) => (pos === 'TD' ? 'DEF' : pos)

const getPosColor = (rawPos) => {
  const pos = normalizePos(rawPos)
  switch (pos) {
    case 'QB': return 'text-red-400 border-red-900/50 bg-red-900/10'
    case 'RB': return 'text-green-400 border-green-900/50 bg-green-900/10'
    case 'WR': return 'text-blue-400 border-blue-900/50 bg-blue-900/10'
    case 'TE': return 'text-orange-400 border-orange-900/50 bg-orange-900/10'
    case 'K': return 'text-purple-400 border-purple-900/50 bg-purple-900/10'
    case 'DEF': return 'text-slate-400 border-slate-600 bg-slate-800'
    default: return 'text-gray-400 border-gray-700'
  }
}

export default function DraftBoard({ token, activeOwnerId }) {
  // --- DRAFT STATE ---
  const [owners, setOwners] = useState([])
  const [players, setPlayers] = useState([]) 
  const [winnerId, setWinnerId] = useState(activeOwnerId) 
  const [sessionId, setSessionId] = useState(`TEST_${new Date().toISOString().slice(0,10)}`)
  const [history, setHistory] = useState([])

  // --- AUCTION BLOCK STATE ---
  const [playerName, setPlayerName] = useState('')
  const [bidAmount, setBidAmount] = useState(1)
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  
  // NEW: Position Filter State
  const [posFilter, setPosFilter] = useState('ALL')

  // --- TIMER STATE ---
  const [timeLeft, setTimeLeft] = useState(10) // Default start time
  const [isTimerRunning, setIsTimerRunning] = useState(false)
  const timerRef = useRef(null)

  // --- DATA LOADING ---
  useEffect(() => {
    if (token) {
      axios.get('http://127.0.0.1:8000/owners').then(res => setOwners(res.data))
      axios.get('http://127.0.0.1:8000/players').then(res => setPlayers(res.data))
      fetchHistory()
    }
  }, [token, sessionId])

  useEffect(() => {
    if (activeOwnerId) setWinnerId(activeOwnerId)
  }, [activeOwnerId])

  const fetchHistory = () => {
    axios.get(`http://127.0.0.1:8000/draft-history?session_id=${sessionId}`)
      .then(res => setHistory(res.data))
      .catch(err => console.log("No history yet"))
  }

  // --- DRAFT ACTION (Moved up for auto-call) ---
  // Wrapped in useCallback so useEffect can reference it
  const handleDraft = useCallback(() => {
    if (!winnerId) return alert("Please select a winner!")
    
    // Normalize logic for finding player
    const foundPlayer = players.find(p => p.name.toLowerCase() === playerName.toLowerCase())
    
    if (!foundPlayer) {
        setIsTimerRunning(false)
        return alert("❌ Player not found! Check spelling.")
    }
    if (history.some(h => h.player_id === foundPlayer.id)) {
        setIsTimerRunning(false)
        return alert("❌ Player already drafted!")
    }

    const winnerPicks = history.filter(h => h.owner_id === winnerId)
    if (winnerPicks.length >= ROSTER_SIZE) {
        setIsTimerRunning(false)
        return alert("❌ This owner's roster is full!")
    }

    const payload = {
      owner_id: winnerId,
      player_id: foundPlayer.id,
      amount: bidAmount,
      session_id: sessionId
    }

    axios.post('http://127.0.0.1:8000/draft-pick', payload)
      .then(() => {
        setPlayerName('')
        setBidAmount(1)
        if (timerRef.current) clearInterval(timerRef.current)
        setIsTimerRunning(false)
        setTimeLeft(10) 
        fetchHistory()
      })
      .catch(err => {
          setIsTimerRunning(false)
          alert("Draft failed! " + (err.response?.data?.detail || "Check backend."))
      })
  }, [winnerId, playerName, players, history, bidAmount, sessionId])

  // --- TIMER LOGIC ---
  const startTimer = () => {
    if (!playerName) return alert("Enter a player name first!")
    
    if (timerRef.current) clearInterval(timerRef.current)
    setTimeLeft(5) // Start countdown from 5
    setIsTimerRunning(true)

    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  const resetTimer = () => {
      if (timerRef.current) clearInterval(timerRef.current)
      setIsTimerRunning(false)
      setTimeLeft(10)
  }

  // --- NEW: AUTO-DRAFT WATCHER ---
  useEffect(() => {
    // If timer hits 0 AND it was actually running (not just initial state), draft!
    if (timeLeft === 0 && isTimerRunning) {
        handleDraft()
    }
  }, [timeLeft, isTimerRunning, handleDraft])


  // --- SEARCH LOGIC ---
  const handleSearchChange = (e) => {
    const val = e.target.value
    setPlayerName(val)
    if (val.length > 1) {
      const draftedIds = new Set(history.map(h => h.player_id))
      
      const matches = players.filter(p => {
        const nameMatch = p.name.toLowerCase().includes(val.toLowerCase())
        const notDrafted = !draftedIds.has(p.id)
        // Position Filter Logic
        const pPos = normalizePos(p.position || 'UNK')
        const posMatch = posFilter === 'ALL' || pPos === posFilter
        
        return nameMatch && notDrafted && posMatch
      }).slice(0, 8) 
      
      setSuggestions(matches)
      setShowSuggestions(true)
    } else {
      setShowSuggestions(false)
    }
  }

  const selectSuggestion = (player) => {
    setPlayerName(player.name)
    setShowSuggestions(false)
  }

  const handleFinalize = () => {
    if (!window.confirm("End draft? This locks rosters.")) return
    axios.post('http://127.0.0.1:8000/admin/finalize-draft')
      .then(res => {
         if (res.data.status === 'error') alert("Cannot Finalize:\n" + res.data.messages.join("\n"))
         else { alert("🎉 " + res.data.message); window.location.href = "/" }
      })
  }

  // --- STATS HELPER ---
  const getOwnerStats = (ownerId) => {
    const ownerPicks = history.filter(pick => pick.owner_id === ownerId)
    const spent = ownerPicks.reduce((sum, pick) => sum + pick.amount, 0)
    const remainingBudget = 200 - spent
    const emptySpots = ROSTER_SIZE - ownerPicks.length
    const maxBid = emptySpots > 0 ? remainingBudget - (emptySpots - 1) : 0

    const posCounts = {}
    POSITIONS.forEach(pos => posCounts[pos] = 0)
    ownerPicks.forEach(pick => {
      const p = players.find(pl => pl.id === pick.player_id)
      if (p) {
          const normPos = normalizePos(p.position)
          if(posCounts[normPos] !== undefined) posCounts[normPos]++
      }
    })

    return { spent, remaining: remainingBudget, count: ownerPicks.length, emptySpots, maxBid, posCounts }
  }

  // --- NOMINATOR LOGIC ---
  const getNominatorId = () => {
    if (owners.length === 0) return null
    const sortedOwners = [...owners].sort((a,b) => a.id - b.id)
    const nominatorIndex = history.length % owners.length
    return sortedOwners[nominatorIndex].id
  }

  const currentNominatorId = getNominatorId()
  const activeStats = winnerId ? getOwnerStats(winnerId) : null

  return (
    <div>
      {/* CONTROL PANEL */}
      <div className="sticky top-0 z-20 bg-slate-900 border-b border-yellow-600 shadow-2xl pb-4 -mx-4 md:-mx-6 px-4 md:px-6 pt-2">
        
        {/* STATUS BAR */}
        <div className="flex justify-between items-center py-2 bg-black/40 text-xs text-slate-400 mb-4 rounded px-2 border border-slate-800">
           <div className="flex gap-4">
             <span>Session: <span className="text-slate-200">{sessionId}</span></span>
             <span>Max Roster: <span className="text-slate-200">{ROSTER_SIZE}</span></span>
           </div>
           <button onClick={handleFinalize} className="bg-red-900/50 hover:bg-red-600 border border-red-700 text-red-100 px-3 py-1 rounded font-bold transition text-[10px] uppercase tracking-wider">
             🛑 End Draft
           </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
          
          {/* LEFT: PLAYER SELECTION */}
          <div className="md:col-span-5 relative">
               {/* NEW: POSITION FILTERS */}
               <div className="flex gap-1 mb-2 overflow-x-auto pb-1">
                   {['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DEF'].map(pos => (
                       <button 
                         key={pos}
                         onClick={() => setPosFilter(pos)}
                         className={`text-[10px] font-bold px-2 py-1 rounded border transition ${
                             posFilter === pos 
                             ? 'bg-yellow-500 text-black border-yellow-500' 
                             : 'bg-slate-800 text-slate-400 border-slate-700 hover:border-slate-500'
                         }`}
                       >
                           {pos}
                       </button>
                   ))}
               </div>

               <label className="block text-slate-500 text-xs mb-1 font-bold uppercase">Player Search</label>
               <input 
                  className="w-full p-3 rounded bg-slate-800 border border-slate-600 focus:border-yellow-500 text-lg font-bold outline-none placeholder:text-slate-600" 
                  value={playerName} 
                  onChange={handleSearchChange} 
                  placeholder={`Search ${posFilter === 'ALL' ? 'Players' : posFilter}...`} 
                  autoComplete="off"
               />
               {showSuggestions && suggestions.length > 0 && (
                 <ul className="absolute z-50 w-full bg-slate-800 border border-slate-600 mt-1 rounded shadow-xl max-h-60 overflow-y-auto">
                   {suggestions.map(p => (
                     <li key={p.id} onClick={() => selectSuggestion(p)} className="p-2 hover:bg-slate-700 cursor-pointer flex justify-between border-b border-slate-700">
                       <span className="text-sm font-bold text-slate-200">{p.name}</span>
                       <span className={`text-[10px] px-1.5 py-0.5 rounded ${getPosColor(p.position)}`}>
                           {normalizePos(p.position)} - {p.nfl_team}
                       </span>
                     </li>
                   ))}
                 </ul>
               )}
          </div>

          {/* MIDDLE: BIDDER CONTROLS (Grouped) */}
          <div className="md:col-span-4 bg-slate-800/50 p-2 rounded border border-slate-700 flex flex-col justify-between">
              <div>
                <label className="block text-slate-500 text-[10px] uppercase font-bold mb-1">Winning Bidder</label>
                <select 
                    className="w-full bg-slate-800 text-white border border-slate-600 rounded p-1.5 text-sm font-bold outline-none focus:border-yellow-500"
                    value={winnerId || ""}
                    onChange={(e) => setWinnerId(parseInt(e.target.value))}
                >
                    {owners.map(o => <option key={o.id} value={o.id}>{o.username}</option>)}
                </select>
                {activeStats && (
                    <div className="text-[10px] text-green-400 font-mono mt-1 text-right">
                    Max: ${activeStats.maxBid}
                    </div>
                )}
              </div>

              <div className="mt-2">
                <label className="block text-slate-500 text-[10px] uppercase font-bold mb-1">Bid Amount</label>
                <div className="flex items-center">
                    <button onClick={()=>setBidAmount(Math.max(1, bidAmount-1))} className="w-8 py-2 bg-slate-700 hover:bg-slate-600 rounded-l font-bold">-</button>
                    <input type="number" className="flex-1 text-center bg-slate-900 text-xl font-bold border-y border-slate-700 py-1 outline-none text-yellow-500" value={bidAmount} onChange={e=>setBidAmount(parseInt(e.target.value))} />
                    <button onClick={()=>setBidAmount(bidAmount+1)} className="w-8 py-2 bg-slate-700 hover:bg-slate-600 rounded-r font-bold">+</button>
                </div>
              </div>
          </div>

          {/* RIGHT: TIMER & ACTION */}
          <div className="md:col-span-3 flex gap-2 h-full">
            <button 
                onClick={handleDraft} 
                className="flex-grow bg-yellow-500 hover:bg-yellow-400 text-black font-black text-xl rounded uppercase tracking-tighter shadow-[0_0_20px_rgba(234,179,8,0.4)] transition active:scale-95"
            >
                SOLD! 🔨
            </button>
            
            <div className="flex flex-col gap-1 w-20">
              <div className={`h-full flex items-center justify-center font-mono text-3xl font-bold border rounded bg-black ${timeLeft <= 3 && isTimerRunning ? 'text-red-500 border-red-500 animate-pulse' : 'text-white border-slate-700'}`}>
                {timeLeft}s
              </div>
              <button 
                  onClick={isTimerRunning ? resetTimer : startTimer} 
                  className={`text-[10px] py-1 rounded font-bold uppercase ${isTimerRunning ? 'bg-slate-700 text-slate-300' : 'bg-green-600 text-white'}`}
              >
                {isTimerRunning ? "RESET" : "START"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* MAIN GRID */}
      <div className="pt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {owners.map(owner => {
            const stats = getOwnerStats(owner.id)
            const isNominator = owner.id === currentNominatorId
            const isSelectedWinner = owner.id === winnerId 
            const myPicks = history.filter(h => h.owner_id === owner.id)

            return (
              <div key={owner.id} className={`flex flex-col h-96 rounded-lg border relative transition-all ${isSelectedWinner ? 'ring-2 ring-yellow-500 shadow-xl' : ''} ${isNominator ? 'border-blue-500 bg-slate-800' : 'border-slate-800 bg-slate-900/50'}`}>
                
                {isNominator && (
                   <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-[10px] font-bold px-3 py-1 rounded-full shadow-lg z-10 uppercase tracking-wider">
                     Nominating
                   </div>
                )}

                {/* CARD HEADER */}
                <div className={`p-3 border-b flex justify-between items-end bg-black/20 rounded-t-lg ${isNominator ? 'border-blue-500/30' : 'border-slate-700'}`}>
                  <div className="w-2/3">
                    <div className={`font-bold truncate ${isNominator ? 'text-blue-300' : 'text-slate-200'}`}>{owner.username}</div>
                    {/* NEW: Expanded Position Summary (K/DEF Included) */}
                    <div className="flex flex-wrap gap-1 mt-1">
                      {POSITIONS.map(pos => (
                          <span key={pos} className={`text-[9px] px-1 rounded ${stats.posCounts[pos] > 0 ? 'bg-slate-700 text-white border border-slate-600' : 'text-slate-600 border border-transparent'}`}>
                            {pos}:{stats.posCounts[pos]}
                          </span>
                       ))}
                    </div>
                  </div>
                  <div className="text-right w-1/3">
                    <div className={`text-2xl font-mono font-bold leading-none ${stats.remaining < 10 ? "text-red-400" : "text-green-400"}`}>${stats.remaining}</div>
                    <div className="text-[9px] text-slate-500 uppercase">Max: ${stats.maxBid}</div>
                  </div>
                </div>

                {/* PICKS LIST */}
                <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
                  {myPicks.map(p => {
                    const playerDetails = players.find(pl => pl.id === p.player_id)
                    const pos = normalizePos(playerDetails?.position || 'UNK') // Normalizing here
                    const colorClass = getPosColor(pos)

                    return (
                      <div key={p.id} className={`flex justify-between items-center p-1.5 rounded border text-sm ${colorClass}`}>
                          <div className="flex gap-2 items-center overflow-hidden">
                            <span className="font-bold text-[10px] w-6 shrink-0 opacity-70">{pos}</span>
                            <span className="truncate font-medium">{playerDetails?.name}</span>
                          </div>
                          <span className="font-mono font-bold opacity-80">${p.amount}</span>
                      </div>
                    )
                  })}
                  {[...Array(stats.emptySpots)].map((_, i) => (
                    <div key={i} className="h-6 border border-dashed border-slate-800 rounded bg-slate-900/30"></div>
                  ))}
                </div>
              </div>
            )
        })}
      </div>
    </div>
  )
}