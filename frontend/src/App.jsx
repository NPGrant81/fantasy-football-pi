import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import axios from 'axios'
import './App.css'

// Import Components
import Layout from './components/Layout'
import LeagueSelector from './components/LeagueSelector'
import LeagueAdvisor from './components/LeagueAdvisor' // <--- IMPORT IS ALREADY HERE (Good!)

// Import Pages
import Home from './pages/Home'
import MyTeam from './pages/MyTeam'
import Matchups from './pages/Matchups'
import GameCenter from './pages/GameCenter'
import CommissionerDashboard from './pages/CommissionerDashboard'
import Dashboard from './pages/Dashboard';
import DraftBoard from './pages/DraftBoard'; 
import Waivers from './pages/Waivers';     // <-- You likely need this one too!
import SiteAdmin from './pages/SiteAdmin'; // <-- THIS is the one causing the current crash

function App() {
  // --- GLOBAL STATE ---
  const [token, setToken] = useState(localStorage.getItem('fantasyToken'))
  const [activeLeagueId, setActiveLeagueId] = useState(localStorage.getItem('fantasyLeagueId'))
  
  // User Info
  const [activeOwnerId, setActiveOwnerId] = useState(null)
  const [username, setUsername] = useState('')

  // Login Inputs
  const [userInput, setUserInput] = useState('')
  const [passInput, setPassInput] = useState('')

  // --- 1. AUTH CHECK ---
  useEffect(() => {
    if (token) {
      axios.get('http://127.0.0.1:8000/me', { headers: { Authorization: `Bearer ${token}` } })
        .then(res => {
          setActiveOwnerId(res.data.user_id)
          setUsername(res.data.username)
        })
        .catch(() => handleLogout()) 
    }
  }, [token])

  // --- 2. LOGIN ---
  const handleLogin = (e) => {
    e.preventDefault()
    const formData = new FormData()
    formData.append('username', userInput)
    formData.append('password', passInput)

    axios.post('http://127.0.0.1:8000/token', formData)
      .then(res => {
        setToken(res.data.access_token)
        localStorage.setItem('fantasyToken', res.data.access_token)
      })
      .catch(err => alert("Login Failed"))
  }

  // --- 3. LOGOUT ---
  const handleLogout = () => {
    setToken(null)
    setActiveOwnerId(null)
    setUsername('')
    localStorage.removeItem('fantasyToken')
  }

  // --- 4. SWITCH LEAGUE ---
  const handleSwitchLeague = () => {
    setActiveLeagueId(null)
    localStorage.removeItem('fantasyLeagueId')
    handleLogout()
  }

  // ==========================================
  // TRAFFIC COP (Render Logic)
  // ==========================================

  // PATH A: No League Selected
  if (!activeLeagueId) {
    return (
      <LeagueSelector 
        onLeagueSelect={(id) => {
          setActiveLeagueId(id)
          localStorage.setItem('fantasyLeagueId', id)
        }} 
        token={token} // Pass token so we can fetch leagues!
      />
    )
  }

  // PATH B: Not Logged In
  if (!token) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white">
        <button onClick={handleSwitchLeague} className="mb-6 text-xs text-slate-500 hover:text-white transition">
          ← Switch League
        </button>
        <form onSubmit={handleLogin} className="bg-slate-800 p-8 rounded-lg shadow-2xl w-96 border border-slate-700">
          <h2 className="text-3xl font-black mb-6 text-center text-yellow-500 tracking-tighter">WAR ROOM LOGIN</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Username</label>
              <input className="w-full p-3 rounded bg-slate-900 border border-slate-600 text-white focus:border-yellow-500 outline-none" value={userInput} onChange={e=>setUserInput(e.target.value)} placeholder="Enter username" />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Password</label>
              <input type="password" className="w-full p-3 rounded bg-slate-900 border border-slate-600 text-white focus:border-yellow-500 outline-none" value={passInput} onChange={e=>setPassInput(e.target.value)} placeholder="Enter password" />
            </div>
          </div>
          <button className="w-full mt-8 bg-gradient-to-r from-green-600 to-green-500 py-3 rounded font-bold hover:shadow-lg hover:from-green-500 hover:to-green-400 transition transform hover:-translate-y-0.5">ENTER</button>
        </form>
      </div>
    )
  }

  // PATH C: FULL APP (Logged In + League Selected)
// Updated App.jsx Routes
  return (
    <BrowserRouter>
      {/* Layout provides the Sidebar/Nav and includes the Global Search */}
      <Layout username={username} leagueId={activeLeagueId}>
        
        <Routes>
          {/* NEW: The Manager Dashboard is now the Home Page */}
          <Route path="/" element={<Dashboard ownerId={activeOwnerId} />} />
          
          {/* MODULARIZED: Your new high-performance Draft Board */}
          <Route path="/draft" element={<DraftBoard token={token} activeOwnerId={activeOwnerId} />} />
          
          {/* SALVAGED: Existing features */}
          <Route path="/team" element={<MyTeam token={token} activeOwnerId={activeOwnerId} />} />
          <Route path="/matchups" element={<Matchups token={token} />} />
          <Route path="/matchup/:id" element={<GameCenter token={token} />} />
          
          {/* NEW: Admin Tools we built on the beach */}
          <Route path="/admin" element={<SiteAdmin token={token} />} />
          <Route path="/commissioner" element={<CommissionerDashboard token={token} />} />
          
          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" />} />
          
          {/* Replace the 🚧 Construction Zone line with this */}
          <Route path="/waivers" element={<Waivers token={token} activeOwnerId={activeOwnerId} />} />

        </Routes>

        {/* THE AGENT: Stays floating for context-aware help */}
        <LeagueAdvisor token={token} />


      </Layout>
    </BrowserRouter>
  )
}

export default App