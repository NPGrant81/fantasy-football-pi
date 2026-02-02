import { useEffect, useState, useRef } from 'react'
import axios from 'axios'
import './App.css'

// --- CONFIGURATION ---
const ROSTER_SIZE = 14
const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']

const getPosColor = (pos) => {
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

function App() {
  // --- AUTH STATE ---
  const [token, setToken] = useState(localStorage.getItem('fantasyToken'))
  const [usernameInput, setUsernameInput] = useState('')
  const [passwordInput, setPasswordInput] = useState('')

  // --- DRAFT STATE ---
  const [owners, setOwners] = useState([])
  const [players, setPlayers] = useState([]) 
  const [activeOwnerId, setActiveOwnerId] = useState(null) // Who is logged in?
  const [winnerId, setWinnerId] = useState(null) // Who is WINNING the current bid?
  const [sessionId, setSessionId] = useState(`TEST_${new Date().toISOString().slice(0,10)}`)
  const [history, setHistory] = useState([])

  // --- AUCTION BLOCK STATE ---
  const [playerName, setPlayerName] = useState('')
  const [bidAmount, setBidAmount] = useState(1)
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  
  // --- TIMER STATE ---
  const [timeLeft, setTimeLeft] = useState(5)
  const timerRef = useRef(null)

  // --- LOGIN LOGIC ---
  const handleLogin = (e) => {
    e.preventDefault()
    const formData = new FormData()
    formData.append('username', usernameInput)
    formData.append('password', passwordInput)

    axios.post('http://127.0.0.1:8000/token', formData)
      .then(res => {
        const newToken = res.data.access_token
        setToken(newToken)
        localStorage.setItem('fantasyToken', newToken)
        fetchUserInfo(newToken)
      })
      .catch(err => alert("Login Failed! Try 'password123'"))
  }

  const fetchUserInfo = (tokenToUse) => {
    axios.get('http://127.0.0.1:8000/me', { headers: { Authorization: `Bearer ${tokenToUse}` } })
      .then(res => {
        setActiveOwnerId(res.data.user_id)
        setWinnerId(res.data.user_id) // Default the winner to me initially
      })
      .catch(() => handleLogout()) 
  }

  const handleLogout = () => {
    setToken(null)
    localStorage.removeItem('fantasyToken')
    setActiveOwnerId(null)
  }

  // --- DATA LOADING ---
  useEffect(() => {
    if (token) {
      fetchUserInfo(token)
      axios.get('http://127.0.0.1:8000/owners').then(res => setOwners(res.data))
      axios.get('http://127.0.0.1:8000/players').then(res => setPlayers(res.data))
      fetchHistory()
    }
  }, [token, sessionId])

  const fetchHistory = () => {
    axios.get(`http://127.0.0.1:8000/draft-history?session_id=${sessionId}`)
      .then(res => setHistory(res.data))
      .catch(err => console.log("No history yet"))
  }

  // --- TIMER LOGIC ---
  const startTimer = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    setTimeLeft(5) 
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
    startTimer()
  }

  // --- SEARCH & DRAFT LOGIC ---
  const handleSearchChange = (e) => {
    const val = e.target.value
    setPlayerName(val)
    if (val.length > 1) {
      const draftedIds = new Set(history.map(h => h.player_id))
      const matches = players.filter(p => 
        p.name.toLowerCase().includes(val.toLowerCase()) && 
        !draftedIds.has(p.id)
      ).slice(0, 8) 
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

  const handleDraft = () => {
    if (!activeOwnerId) return alert("You must be logged in!")
    // Use winnerId (from dropdown) instead of activeOwnerId
    if (!winnerId) return alert("Please select a winner!")

    const foundPlayer = players.find(p => p.name.toLowerCase() === playerName.toLowerCase())
    if (!foundPlayer) return alert("❌ Player not found in database!")
    if (history.some(h => h.player_id === foundPlayer.id)) return alert("❌ Player already drafted!")

    // Validate Roster Limits for the WINNER
    const winnerPicks = history.filter(h => h.owner_id === winnerId)
    if (winnerPicks.length >= ROSTER_SIZE) return alert("❌ This owner's roster is full!")

    const payload = {
      owner_id: winnerId, // <--- Assign to the selected winner
      player_id: foundPlayer.id,
      amount: bidAmount,
      session_id: sessionId
    }

    axios.post('http://127.0.0.1:8000/draft-pick', payload)
      .then(() => {
        setPlayerName('')
        setBidAmount(1)
        if (timerRef.current) clearInterval(timerRef.current)
        setTimeLeft(5) 
        fetchHistory()
      })
      .catch(err => alert("Draft failed! " + (err.response?.data?.detail || "Check backend.")))
  }

  // --- STATS HELPER ---
  const getOwnerStats = (ownerId) => {
    const ownerPicks = history.filter(pick => pick.owner_id === ownerId)
    const spent = ownerPicks.reduce((sum, pick) => sum + pick.amount, 0)
    const count = ownerPicks.length
    const remainingBudget = 200 - spent
    const emptySpots = ROSTER_SIZE - count
    const maxBid = emptySpots > 0 ? remainingBudget - (emptySpots - 1) : 0

    const posCounts = {}
    POSITIONS.forEach(pos => posCounts[pos] = 0)
    ownerPicks.forEach(pick => {
      const p = players.find(pl => pl.id === pick.player_id)
      if (p && p.position) posCounts[p.position] = (posCounts[p.position] || 0) + 1
    })

    return { spent, remaining: remainingBudget, count, emptySpots, maxBid, posCounts }
  }

  // --- 4. NEW: FIND CURRENT NOMINATOR ---
  // Logic: The turn rotates 1, 2, 3... based on total picks made.
  const getNominatorId = () => {
    if (owners.length === 0) return null
    // Sort owners by ID to ensure the order is always consistent (1, 2, 3...)
    const sortedOwners = [...owners].sort((a,b) => a.id - b.id)
    const nominatorIndex = history.length % owners.length
    return sortedOwners[nominatorIndex].id
  }

  const currentNominatorId = getNominatorId()

  // --- RENDER LOGIN ---
  if (!token) return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center text-white">
      <form onSubmit={handleLogin} className="bg-slate-800 p-8 rounded shadow-lg w-96 border border-slate-700">
        <h2 className="text-3xl font-bold mb-6 text-center text-yellow-400">🏈 War Room Login</h2>
        <input className="w-full p-2 mb-4 rounded bg-slate-700" value={usernameInput} onChange={e=>setUsernameInput(e.target.value)} placeholder="Username" />
        <input type="password" className="w-full p-2 mb-6 rounded bg-slate-700" value={passwordInput} onChange={e=>setPasswordInput(e.target.value)} placeholder="Password" />
        <button className="w-full bg-green-600 py-3 rounded font-bold hover:bg-green-500">ENTER</button>
      </form>
    </div>
  )

  const activeStats = winnerId ? getOwnerStats(winnerId) : null

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      
      {/* HEADER / CONTROL PANEL */}
      <div className="sticky top-0 z-50 bg-slate-900 border-b border-yellow-600 shadow-2xl pb-4">
        <div className="flex justify-between items-center px-6 py-2 bg-black/40 text-xs text-slate-400">
           <div className="flex gap-4">
             <span>Session: {sessionId}</span>
             <span>Max Roster: {ROSTER_SIZE}</span>
           </div>
           <button onClick={handleLogout} className="text-red-400 hover:text-red-300">Logout</button>
        </div>

        <div className="grid grid-cols-12 gap-4 px-6 mt-4 items-end">
          
          {/* WINNER SELECTOR (COMMISSIONER MODE) */}
          <div className="col-span-3">
             <label className="block text-slate-400 text-xs uppercase tracking-widest font-bold mb-1">
               Winning Bidder
             </label>
             {/* 1. NEW: DROPDOWN SELECTOR */}
             <select 
                className="w-full bg-slate-800 text-white border border-slate-600 rounded p-2 text-lg font-bold outline-none focus:border-yellow-500"
                value={winnerId || ""}
                onChange={(e) => setWinnerId(parseInt(e.target.value))}
             >
               {owners.map(o => (
                 <option key={o.id} value={o.id}>{o.username}</option>
               ))}
             </select>

             {activeStats && (
               <div className="text-xs text-green-400 font-mono mt-1">
                 Max Bid: <span className="text-xl font-bold">${activeStats.maxBid}</span>
               </div>
             )}
          </div>

          {/* INPUTS */}
          <div className="col-span-6 flex gap-4">
            <div className="relative flex-grow">
               <label className="block text-slate-500 text-xs mb-1">Player</label>
               <input 
                  className="w-full p-3 rounded bg-slate-800 border border-slate-600 focus:border-yellow-500 text-lg font-bold outline-none" 
                  value={playerName} onChange={handleSearchChange} placeholder="Search Player..." autoComplete="off"
               />
               {showSuggestions && suggestions.length > 0 && (
                 <ul className="absolute z-50 w-full bg-slate-800 border border-slate-600 mt-1 rounded shadow-xl max-h-60 overflow-y-auto">
                   {suggestions.map(p => (
                     <li key={p.id} onClick={() => selectSuggestion(p)} className="p-2 hover:bg-slate-700 cursor-pointer flex justify-between border-b border-slate-700">
                       <span>{p.name}</span>
                       <span className={`text-xs px-2 rounded ${getPosColor(p.position)}`}>{p.position} - {p.nfl_team}</span>
                     </li>
                   ))}
                 </ul>
               )}
            </div>
            
            <div className="w-32">
              <label className="block text-slate-500 text-xs mb-1">Bid ($)</label>
              <div className="flex items-center">
                 <button onClick={()=>setBidAmount(Math.max(1, bidAmount-1))} className="px-3 py-3 bg-slate-700 hover:bg-slate-600 rounded-l font-bold">-</button>
                 <input type="number" className="w-full text-center bg-slate-800 text-xl font-bold border-y border-slate-600 py-2 outline-none" value={bidAmount} onChange={e=>setBidAmount(parseInt(e.target.value))} />
                 <button onClick={()=>setBidAmount(bidAmount+1)} className="px-3 py-3 bg-slate-700 hover:bg-slate-600 rounded-r font-bold">+</button>
              </div>
            </div>
          </div>

          {/* TIMER */}
          <div className="col-span-3 flex gap-2">
            <div className="flex-grow">
               <button 
                  onClick={handleDraft} 
                  className="w-full h-full bg-yellow-500 hover:bg-yellow-400 text-black font-black text-xl rounded uppercase tracking-tighter shadow-[0_0_20px_rgba(234,179,8,0.4)] transition"
               >
                 SOLD! 🔨
               </button>
            </div>
            
            <div className="flex flex-col gap-1 w-24">
              <div className={`text-center font-mono text-3xl font-bold border rounded bg-black ${timeLeft === 0 ? 'text-red-500 border-red-500' : 'text-white border-slate-700'}`}>
                {timeLeft}s
              </div>
              <button onClick={resetTimer} className="bg-slate-700 text-xs py-1 rounded hover:bg-slate-600">
                {timeLeft < 5 && timeLeft > 0 ? "RESET ↻" : "START"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* MAIN GRID */}
      <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {owners.map(owner => {
            const stats = getOwnerStats(owner.id)
            // 2. NEW: HIGHLIGHT NOMINATOR
            const isNominator = owner.id === currentNominatorId
            // Highlight if I selected this person in the dropdown
            const isSelectedWinner = owner.id === winnerId 
            const myPicks = history.filter(h => h.owner_id === owner.id)

            return (
              <div key={owner.id} className={`flex flex-col h-96 rounded-lg border relative transition-all ${isSelectedWinner ? 'ring-2 ring-yellow-500 shadow-xl' : ''} ${isNominator ? 'border-blue-500 bg-slate-800' : 'border-slate-800 bg-slate-900/50'}`}>
                
                {/* 3. NOMINATOR BADGE */}
                {isNominator && (
                   <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-[10px] font-bold px-3 py-1 rounded-full shadow-lg z-10 uppercase tracking-wider">
                     📢 Nominating
                   </div>
                )}

                {/* CARD HEADER */}
                <div className={`p-3 border-b flex justify-between items-end bg-black/20 rounded-t-lg ${isNominator ? 'border-blue-500/30' : 'border-slate-700'}`}>
                  <div>
                    <div className={`font-bold truncate ${isNominator ? 'text-blue-300' : 'text-slate-200'}`}>{owner.username}</div>
                    <div className="text-[10px] text-slate-500 flex gap-2 mt-1">
                      {POSITIONS.slice(0,4).map(pos => (
                         <span key={pos} className={stats.posCounts[pos] === 0 ? 'opacity-30' : 'text-slate-300'}>
                           {pos}:{stats.posCounts[pos]}
                         </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-2xl font-mono font-bold leading-none ${stats.remaining < 10 ? "text-red-400" : "text-green-400"}`}>${stats.remaining}</div>
                    <div className="text-[10px] text-slate-500 uppercase">Max Bid: ${stats.maxBid}</div>
                  </div>
                </div>

                {/* PICKS LIST */}
                <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
                  {myPicks.map(p => {
                    const playerDetails = players.find(pl => pl.id === p.player_id)
                    const pos = playerDetails?.position || 'UNK'
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

export default App