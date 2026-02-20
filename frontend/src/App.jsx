/* eslint-disable no-unused-vars */
import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import apiClient from '@api/client';
import './App.css';

// Import Components
import Layout from './components/Layout';
import LeagueSelector from './components/LeagueSelector';
import LeagueAdvisor from './components/LeagueAdvisor';

// Import Pages (Lazy Loaded)
const MyTeam = lazy(() => import('./pages/team-owner/MyTeam'));
const Matchups = lazy(() => import('./pages/matchups/Matchups'));
const GameCenter = lazy(() => import('./pages/matchups/GameCenter'));
const CommissionerDashboard = lazy(
  () => import('./pages/commissioner/CommissionerDashboard')
);
const Home = lazy(() => import('./pages/home/Home'));
const DraftBoard = lazy(() => import('./pages/DraftBoard'));
const Waivers = lazy(() => import('./pages/WaiverWire'));
const SiteAdmin = lazy(() => import('./pages/admin/SiteAdmin'));
const BugReport = lazy(() => import('./pages/BugReport'));
const AnalyticsDashboard = lazy(() => import('./pages/Analytics/AnalyticsDashboard'));

/* eslint-enable no-unused-vars */

function App() {
  // --- 1.1 GLOBAL STATE ---
  const [token, setToken] = useState(localStorage.getItem('fantasyToken'));
  const [activeLeagueId, setActiveLeagueId] = useState(
    localStorage.getItem('fantasyLeagueId')
  );
  const [activeOwnerId, setActiveOwnerId] = useState(
    localStorage.getItem('user_id')
  );
  const [username, setUsername] = useState('');

  const [userInput, setUserInput] = useState('');
  const [passInput, setPassInput] = useState('');
  const [leagueInput, setLeagueInput] = useState('1'); // Default to "The Big Show" (league ID 1)
  const [error, setError] = useState('');

  // --- 1.2 LOGOUT (Stable reference for effects) ---
  const handleLogout = useCallback(() => {
    setToken(null);
    setActiveOwnerId(null);
    setUsername('');
    localStorage.removeItem('fantasyToken');
    localStorage.removeItem('user_id');
    localStorage.removeItem('fantasyLeagueId');
  }, []);

  // --- 1.3 AUTH CHECK (The Guard) ---
  useEffect(() => {
    if (token) {
      // UPDATED: Pointing to the new nested endpoint
      apiClient
        .get('/auth/me')
        .then((res) => {
          setActiveOwnerId(res.data.user_id);
          setUsername(res.data.username);
        })
        .catch(() => {
          handleLogout();
        });
    }
  }, [token, handleLogout]);

  // --- 1.4 LOGIN HANDLER ---
  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');

    const formData = new URLSearchParams();
    formData.append('username', userInput);
    formData.append('password', passInput);

    try {
      // UPDATED: Standard OAuth2 tokenUrl is now under /auth
      const response = await apiClient.post('/auth/token', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      const { access_token, owner_id } = response.data;

      localStorage.setItem('fantasyToken', access_token);
      localStorage.setItem('user_id', owner_id);
      localStorage.setItem('fantasyLeagueId', leagueInput); // Use user-provided league ID

      setToken(access_token);
      setActiveOwnerId(owner_id);
      setActiveLeagueId(leagueInput);
    } catch (err) {
      console.error('Login Error:', err);
      setError('Login Failed. Check credentials.');
    }
  };

  // --- 2.1 RENDER TRAFFIC COP ---

  // PATH A: Not Logged In
  if (!token) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white">
        <form
          onSubmit={handleLogin}
          className="bg-slate-800 p-8 rounded-lg shadow-2xl w-96 border border-slate-700"
        >
          <div className="flex flex-col items-center mb-6">
            <img
              src={import.meta.env.BASE_URL + 'src/assets/react.svg'}
              alt="FantasyFootball-PI Logo"
              className="w-16 h-16 mb-2"
            />
            <h2 className="text-3xl font-black text-center text-yellow-500 tracking-tighter">
              FantasyFootball-PI Login
            </h2>
          </div>
          {error && (
            <div className="mb-4 text-red-400 text-center text-sm font-bold">
              {error}
            </div>
          )}
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                Username
              </label>
              <input
                className="w-full p-3 rounded bg-slate-900 border border-slate-600 text-white focus:border-yellow-500 outline-none"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                placeholder="Enter username"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                Password
              </label>
              <input
                type="password"
                className="w-full p-3 rounded bg-slate-900 border border-slate-600 text-white focus:border-yellow-500 outline-none"
                value={passInput}
                onChange={(e) => setPassInput(e.target.value)}
                placeholder="Enter password"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                League ID
              </label>
              <input
                type="number"
                className="w-full p-3 rounded bg-slate-900 border border-slate-600 text-white focus:border-yellow-500 outline-none"
                value={leagueInput}
                onChange={(e) => setLeagueInput(e.target.value)}
                placeholder="Enter league ID (default: 1)"
              />
              <p className="text-xs text-slate-500 mt-1">
                Default: 1 (The Big Show)
              </p>
            </div>
          </div>
          <button
            type="submit"
            className="w-full mt-8 bg-gradient-to-r from-green-600 to-green-500 py-3 rounded font-bold hover:shadow-lg transition transform active:scale-95"
          >
            ENTER
          </button>
        </form>
      </div>
    );
  }

  // PATH B: No League Selected
  if (!activeLeagueId) {
    return (
      <LeagueSelector
        onLeagueSelect={(id) => {
          setActiveLeagueId(id);
          localStorage.setItem('fantasyLeagueId', id);
        }}
      />
    );
  }

  // PATH C: FULL APP
  return (
    <BrowserRouter>
      <Layout
        username={username}
        leagueId={activeLeagueId}
        onLogout={handleLogout}
      >
        <Suspense
          fallback={
            <div className="p-8 text-slate-400 animate-pulse">Loading...</div>
          }
        >
          <Routes>
            <Route path="/" element={<Home username={username} />} />
            <Route
              path="/draft"
              element={
                <DraftBoard
                  token={token}
                  activeOwnerId={activeOwnerId}
                  activeLeagueId={activeLeagueId}
                />
              }
            />
            <Route
              path="/team"
              element={<MyTeam activeOwnerId={activeOwnerId} />}
            />
            <Route path="/matchups" element={<Matchups />} />
            <Route path="/matchup/:id" element={<GameCenter />} />
            <Route path="/admin" element={<SiteAdmin />} />
            <Route path="/commissioner" element={<CommissionerDashboard />} />
            <Route
              path="/waivers"
              element={
                <Waivers
                  activeOwnerId={activeOwnerId}
                  username={username}
                  leagueName={activeLeagueId}
                />
              }
            />
            <Route path="/bug-report" element={<BugReport />} />
            <Route path="/analytics" element={<AnalyticsDashboard />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </Suspense>
        <LeagueAdvisor />
      </Layout>
    </BrowserRouter>
  );
}

export default App;
