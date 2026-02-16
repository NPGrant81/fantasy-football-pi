import { useState, useEffect, useCallback } from 'react' // 1.1 Added useCallback
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import axios from 'axios'
import './App.css'

// Import Components
import Layout from './components/Layout'
import LeagueSelector from './components/LeagueSelector'
import LeagueAdvisor from './components/LeagueAdvisor' 

// Import Pages
import MyTeam from './pages/MyTeam'
import Matchups from './pages/Matchups'
import GameCenter from './pages/GameCenter'
import CommissionerDashboard from './pages/CommissionerDashboard'
import Dashboard from './pages/Dashboard';
import DraftBoard from './pages/DraftBoard'; 
import Waivers from './pages/WaiverWire';    
import SiteAdmin from './pages/SiteAdmin'; 

function App() {
  // --- GLOBAL STATE ---
  const [token, setToken] = useState(localStorage.getItem('fantasyToken'))
  const [activeLeagueId, setActiveLeagueId] = useState(localStorage.getItem('fantasyLeagueId'))
  const [activeOwnerId, setActiveOwnerId] = useState(null)
  const [username, setUsername] = useState('') 

  const [userInput, setUserInput] = useState('')
  const [passInput, setPassInput] = useState('')
  const [error, setError] = useState('')

  // --- 1. LOGOUT (MOVED UP) ---
  // 1.1 We wrap this in useCallback so it's a stable reference for the useEffect
  const handleLogout = useCallback(() => {
    setToken(null)
    setActiveOwnerId(null)
    setUsername('')
    localStorage.removeItem('fantasyToken')
    localStorage.removeItem('user_id')
    localStorage.removeItem('fantasyLeagueId')
  }, [])

  // --- 2. AUTH CHECK ---
  useEffect(() => {
    if (token) {
      axios.get('http://127.0.0.1:8000/me', { 
        headers: { Authorization: `Bearer ${token}` } 
      })
      .then(res => {
        setActiveOwnerId(res.data.user_id)
        setUsername(res.data.username)
      })
      .catch(() => handleLogout()) 
    }
  }, [token, handleLogout]) // 2.1 Added handleLogout to dependencies

  // --- 3. LOGIN ---
  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');

    const formData = new URLSearchParams();
    formData.append('username', userInput);
    formData.append('password', passInput);

    try {
      const response = await axios.post('http://127.0.0.1:8000/token', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });

      localStorage.setItem('fantasyToken', response.data.access_token);
      localStorage.setItem('user_id', response.data.owner_id);
      localStorage.setItem('fantasyLeagueId', response.data.league_id);
      
      setToken(response.data.access_token);
      setActiveLeagueId(response.data.league_id);

    } catch (err) {
      console.error("Login Error:", err);
      setError('Login Failed. Check username/password.');
    }
  };

  // ==========================================
  // TRAFFIC COP (Render Logic)
  // ==========================================

  // PATH A: Not Logged In
  if (!token) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white">
        <form onSubmit={handleLogin} className="bg-slate-800 p-8 rounded-lg shadow-2xl w-96 border border-slate-700">
          <h2 className="text-3xl font-black mb-6 text-center text-yellow-500 tracking-tighter">WAR ROOM LOGIN</h2>
          
          {error && <div className="mb-4 text-red-400 text-center text-sm font-bold">{error}</div>}

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Username</label>
              <input 
                className="w-full p-3 rounded bg-slate-900 border border-slate-600 text-white focus:border-yellow-500 outline-none" 
                value={userInput} 
                onChange={e=>setUserInput(e.target.value)} 
                placeholder="Enter username" 
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Password</label>
              <input 
                type="password" 
                className="w-full p-3 rounded bg-slate-900 border border-slate-600 text-white focus:border-yellow-500 outline-none" 
                value={passInput} 
                onChange={e=>setPassInput(e.target.value)} 
                placeholder="Enter password" 
              />
            </div>
          </div>
          <button type="submit" className="w-full mt-8 bg-gradient-to-r from-green-600 to-green-500 py-3 rounded font-bold hover:shadow-lg hover:from-green-500 hover:to-green-400 transition transform hover:-translate-y-0.5">
            ENTER
          </button>
        </form>
      </div>
    )
  }

  // PATH B: No League Selected
  if (!activeLeagueId) {
    return (
      <LeagueSelector 
        onLeagueSelect={(id) => {
          setActiveLeagueId(id)
          localStorage.setItem('fantasyLeagueId', id)
        }} 
        token={token}
      />
    )
  }

  // PATH C: FULL APP
  return (
    <BrowserRouter>
      <Layout username={username} leagueId={activeLeagueId} onLogout={handleLogout}>
        <Routes>
          <Route path="/" element={<Dashboard ownerId={activeOwnerId} />} />
          <Route path="/draft" element={<DraftBoard token={token} activeOwnerId={activeOwnerId} />} />
          <Route path="/team" element={<MyTeam token={token} activeOwnerId={activeOwnerId} />} />
          <Route path="/matchups" element={<Matchups token={token} />} />
          <Route path="/matchup/:id" element={<GameCenter token={token} />} />
          <Route path="/admin" element={<SiteAdmin token={token} />} />
          <Route path="/commissioner" element={<CommissionerDashboard token={token} />} />
          <Route path="/waivers" element={<Waivers token={token} activeOwnerId={activeOwnerId} />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
        <LeagueAdvisor token={token} />
      </Layout>
    </BrowserRouter>
  )
}

export default App