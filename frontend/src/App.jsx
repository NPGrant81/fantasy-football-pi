import { useEffect, useState } from 'react'
import axios from 'axios'
import './App.css'

function App() {
  // --- AUTH STATE ---
  const [token, setToken] = useState(localStorage.getItem('fantasyToken'))
  const [usernameInput, setUsernameInput] = useState('')
  const [passwordInput, setPasswordInput] = useState('')

  // --- DRAFT STATE ---
  const [owners, setOwners] = useState([])
  const [players, setPlayers] = useState([]) 
  const [activeOwnerId, setActiveOwnerId] = useState(null)
  const [sessionId, setSessionId] = useState(`TEST_${new Date().toISOString().slice(0,10)}`)
  const [bidAmount, setBidAmount] = useState(1)
  const [history, setHistory] = useState([])

  // --- SMART SEARCH STATE ---
  const [playerName, setPlayerName] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  
  // --- LOGIN FUNCTION ---
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
      .then(res => setActiveOwnerId(res.data.user_id))
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

  // --- SMART SEARCH LOGIC ---
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
    
    const foundPlayer = players.find(p => p.name.toLowerCase() === playerName.toLowerCase())
    
    if (!foundPlayer) {
      return alert("❌ Player not found in database! Please select from the list.")
    }
    
    if (history.some(h => h.player_id === foundPlayer.id)) {
      return alert("❌ Player already drafted!")
    }

    const payload = {
      owner_id: activeOwnerId,
      player_name: foundPlayer.name,
      amount: bidAmount,
      session_id: sessionId
    }

    axios.post('http://127.0.0.1:8000/draft-pick', payload)
      .then(() => {
        setPlayerName('')
        setBidAmount(1)
        fetchHistory()
      })
      .catch(err => alert("Draft failed! Check backend."))
  }

  const getOwnerStats = (ownerId) => {
    const ownerPicks = history.filter(pick => pick.owner_id === ownerId)
    const spent = ownerPicks.reduce((sum, pick) => sum + pick.amount, 0)
    return { spent, remaining: 200 - spent }
  }

  // --- RENDER: LOGIN SCREEN ---
  if (!token) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-white">
        <form onSubmit={handleLogin} className="bg-slate-800 p-8 rounded shadow-lg w-96 border border-slate-700">
          <h2 className="text-3xl font-bold mb-6 text-center text-yellow-400">🏈 League Login</h2>
          <div className="mb-4">
            <label className="block mb-1 text-slate-400">Username</label>
            <input className="w-full p-2 rounded bg-slate-700" value={usernameInput} onChange={e=>setUsernameInput(e.target.value)} placeholder="e.g. Nick Grant" />
          </div>
          <div className="mb-6">
            <label className="block mb-1 text-slate-400">Password</label>
            <input type="password" className="w-full p-2 rounded bg-slate-700" value={passwordInput} onChange={e=>setPasswordInput(e.target.value)} placeholder="password123" />
          </div>
          <button className="w-full bg-green-600 py-3 rounded font-bold hover:bg-green-500 transition">ENTER WAR ROOM</button>
        </form>
      </div>
    )
  }

  // --- RENDER: DRAFT BOARD ---
  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      <div className="flex justify-between items-center mb-6 pb-4 border-b border-slate-700">
        <h1 className="text-2xl font-bold text-yellow-400">Draft Room</h1>
        <div className="flex gap-4 items-center">
          <label className="text-sm text-slate-400">Session:</label>
          <input value={sessionId} onChange={e=>setSessionId(e.target.value)} className="bg-slate-800 border border-slate-600 px-2 py-1 rounded text-sm font-mono text-green-400" />
          <button onClick={handleLogout} className="text-red-400 text-sm hover:underline">Logout</button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* CONTROL PANEL */}
        <div className="bg-slate-800 p-6 rounded shadow-lg h-fit">
           <h3 className="text-xl font-bold mb-4 border-b border-slate-600 pb-2">Make a Pick</h3>
           
           <div className="mb-4">
             <label className="block text-slate-400 text-sm mb-1">Drafting For:</label>
             <div className="p-2 bg-yellow-900/30 border border-yellow-600 rounded text-yellow-400 font-bold">
               {owners.find(o => o.id === activeOwnerId)?.username || "Unknown"}
             </div>
           </div>

           {/* SMART SEARCH INPUT */}
           <div className="mb-4 relative">
             <label className="block text-slate-400 text-sm mb-1">Player Name</label>
             <input 
                className="w-full p-2 rounded bg-slate-700 text-white focus:outline-none focus:ring-2 focus:ring-yellow-500" 
                value={playerName} 
                onChange={handleSearchChange}
                placeholder="Start typing..." 
                autoComplete="off"
             />
             {showSuggestions && suggestions.length > 0 && (
               <ul className="absolute z-10 w-full bg-slate-700 border border-slate-600 mt-1 rounded shadow-xl max-h-60 overflow-y-auto">
                 {suggestions.map(p => (
                   <li 
                      key={p.id} 
                      onClick={() => selectSuggestion(p)}
                      className="p-2 hover:bg-slate-600 cursor-pointer flex justify-between items-center border-b border-slate-600 last:border-0"
                   >
                     <span>{p.name}</span>
                     <span className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-400">{p.position} - {p.nfl_team}</span>
                   </li>
                 ))}
               </ul>
             )}
           </div>

           <div className="mb-6">
             <label className="block text-slate-400 text-sm mb-1">Bid Amount</label>
             <div className="flex gap-2">
               <button onClick={()=>setBidAmount(Math.max(1, bidAmount-1))} className="px-3 bg-red-600 rounded font-bold hover:bg-red-500">-</button>
               <input type="number" className="w-full text-center bg-slate-700 text-xl font-bold rounded focus:outline-none" value={bidAmount} onChange={e=>setBidAmount(parseInt(e.target.value))} />
               <button onClick={()=>setBidAmount(bidAmount+1)} className="px-3 bg-green-600 rounded font-bold hover:bg-green-500">+</button>
             </div>
           </div>
           
           <button onClick={handleDraft} className="w-full py-4 bg-yellow-500 text-slate-900 font-bold text-xl rounded shadow-lg hover:bg-yellow-400 transition-transform transform active:scale-95">
             DRAFT PLAYER 🔨
           </button>
        </div>

        {/* SCOREBOARD (New Card Design) */}
        <div className="md:col-span-2 grid grid-cols-2 lg:grid-cols-3 gap-4">
          {owners.map(owner => {
            const stats = getOwnerStats(owner.id)
            const isMe = owner.id === activeOwnerId
            const myPicks = history.filter(h => h.owner_id === owner.id)

            return (
              <div key={owner.id} className={`flex flex-col h-80 rounded border relative ${isMe ? 'border-yellow-400 bg-slate-800 shadow-[0_0_15px_rgba(250,204,21,0.2)]' : 'border-slate-700 bg-slate-900'}`}>
                
                {/* HEADER */}
                <div className={`flex justify-between items-center p-3 border-b ${isMe ? 'border-yellow-500/30 bg-yellow-500/10' : 'border-slate-700 bg-slate-800'}`}>
                  <span className={`font-bold truncate pr-2 ${isMe ? 'text-yellow-400' : 'text-slate-200'}`}>
                    {owner.username}
                  </span>
                  <span className={`text-xl font-mono font-bold ${stats.remaining < 10 ? "text-red-400" : "text-green-400"}`}>
                    ${stats.remaining}
                  </span>
                </div>
                
                {/* PLAYER LIST */}
                <div className="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
                  {myPicks.length === 0 && (
                     <div className="h-full flex items-center justify-center text-slate-600 italic text-xs">
                       No picks yet
                     </div>
                  )}

                  {myPicks.map(p => {
                    const playerDetails = players.find(pl => pl.id === p.player_id)
                    return (
                      <div key={p.id} className="flex justify-between items-center bg-slate-800/50 p-2 rounded border border-slate-700/50 hover:border-slate-600 transition">
                        <div className="flex flex-col overflow-hidden">
                          <span className="font-bold text-sm text-white truncate" title={playerDetails?.name}>
                             {playerDetails?.name || "Unknown"}
                          </span>
                          <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                             {playerDetails?.position || "UNK"} • {playerDetails?.nfl_team || "FA"}
                          </span>
                        </div>
                        <span className="font-mono font-bold text-yellow-500 ml-2">
                          ${p.amount}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default App