import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useParams,
  useLocation,
} from 'react-router-dom';
import apiClient from '@api/client';
import './App.css';

// Import Components
import Layout from './components/Layout';
import LeagueSelector from './components/LeagueSelector';
import LeagueAdvisor from './components/LeagueAdvisor';
import { LoadingState } from '@components/common/AsyncState';
import { ThemeProvider } from './context/ThemeContext';

// Import Pages (Lazy Loaded)
const YourLockerRoom = lazy(() => import('./pages/team-owner/YourLockerRoom'));
const LedgerStatementOwner = lazy(
  () => import('./pages/team-owner/LedgerStatementOwner')
);
const Matchups = lazy(() => import('./pages/matchups/Matchups'));
const GameCenter = lazy(() => import('./pages/matchups/GameCenter'));
const CommissionerDashboard = lazy(
  () => import('./pages/commissioner/CommissionerDashboard')
);
const LineupRules = lazy(() => import('./pages/commissioner/LineupRules'));
const ManageOwners = lazy(() => import('./pages/commissioner/ManageOwners'));
const Home = lazy(() => import('./pages/home/Home'));
const DraftBoard = lazy(() => import('./pages/DraftBoard'));
const DraftDayAnalyzer = lazy(() => import('./pages/DraftDayAnalyzer'));
const Waivers = lazy(() => import('./pages/WaiverWire'));
const WaiverRules = lazy(() => import('./pages/WaiverRules'));
const SiteAdmin = lazy(() => import('./pages/admin/SiteAdmin'));
const ManageCommissioners = lazy(
  () => import('./pages/admin/ManageCommissioners')
);
const ManageWaiverRules = lazy(
  () => import('./pages/commissioner/ManageWaiverRules')
);
const ManageTrades = lazy(() => import('./pages/commissioner/ManageTrades'));
const ManageScoringRules = lazy(
  () => import('./pages/commissioner/ManageScoringRules')
);
const ManageDivisions = lazy(
  () => import('./pages/commissioner/ManageDivisions')
);
const KeeperRules = lazy(
  () => import('./pages/commissioner/ManageKeeperRules')
);
const LedgerStatement = lazy(
  () => import('./pages/commissioner/LedgerStatement')
);
const BugReport = lazy(() => import('./pages/BugReport'));
const AnalyticsDashboard = lazy(
  () => import('./pages/Analytics/AnalyticsDashboard')
);
const Keepers = lazy(() => import('./pages/Keepers'));
const PlayoffBracket = lazy(() => import('./pages/playoffs/PlayoffBracket'));

function TeamRoute({ fallbackOwnerId }) {
  const { ownerId } = useParams();
  return <YourLockerRoom activeOwnerId={ownerId || fallbackOwnerId} />;
}

function resolveLayoutPageTitle(pathname) {
  if (pathname === '/') return 'League Dashboard';
  if (pathname === '/draft') return 'Draft Board';
  if (pathname === '/draft-day-analyzer') return 'Draft Day Analyzer';
  if (pathname === '/team' || pathname.startsWith('/team/')) return 'Locker Room';
  if (pathname === '/ledger') return 'My Ledger Statement';
  if (pathname === '/matchups') return 'Matchups';
  if (pathname.startsWith('/matchup/')) return 'Game Center';
  if (pathname === '/admin') return 'Site Admin';
  if (pathname === '/admin/manage-commissioners') return 'Invite / Manage Commissioners';
  if (pathname === '/commissioner') return 'Commissioner Control Panel';
  if (pathname === '/commissioner/lineup-rules') return 'Lineup Rules';
  if (pathname === '/commissioner/manage-owners') return 'Manage Owners';
  if (pathname === '/commissioner/manage-waiver-rules') return 'Manage Waiver Rules';
  if (pathname === '/commissioner/manage-trades') return 'Manage Trades';
  if (pathname === '/commissioner/manage-scoring-rules') return 'Manage Scoring Rules';
  if (pathname === '/commissioner/manage-divisions') return 'Manage Divisions';
  if (pathname === '/commissioner/keeper-rules') return 'Keeper Rules';
  if (pathname === '/commissioner/ledger-statement') return 'Ledger Statement';
  if (pathname === '/waivers') return 'Waiver Wire';
  if (pathname === '/waiver-rules') return 'Waiver Rules';
  if (pathname === '/bug-report') return 'Bug Report';
  if (pathname === '/keepers') return 'Manage Keepers';
  if (pathname === '/analytics') return 'League Analytics';
  if (pathname === '/playoffs') return 'Playoff Bracket';
  return 'Fantasy Pi';
}

function AuthenticatedShell({
  username,
  activeLeagueId,
  handleLogout,
  layoutAlert,
  token,
  activeOwnerId,
}) {
  const location = useLocation();
  const headerTitle = resolveLayoutPageTitle(location.pathname);

  return (
    <Layout
      username={username}
      leagueId={activeLeagueId}
      alert={layoutAlert}
      onLogout={handleLogout}
      pageTitle={headerTitle}
    >
      <Suspense
        fallback={
          <div className="p-8 text-slate-400">
            <LoadingState message="Loading..." />
          </div>
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
            path="/draft-day-analyzer"
            element={
              <DraftDayAnalyzer
                activeOwnerId={activeOwnerId}
                activeLeagueId={activeLeagueId}
              />
            }
          />
          <Route
            path="/team"
            element={<YourLockerRoom activeOwnerId={activeOwnerId} />}
          />
          <Route path="/ledger" element={<LedgerStatementOwner />} />
          <Route
            path="/team/:ownerId"
            element={<TeamRoute fallbackOwnerId={activeOwnerId} />}
          />
          <Route path="/matchups" element={<Matchups />} />
          <Route path="/matchup/:id" element={<GameCenter />} />
          <Route path="/admin" element={<SiteAdmin />} />
          <Route
            path="/admin/manage-commissioners"
            element={<ManageCommissioners />}
          />
          <Route path="/commissioner" element={<CommissionerDashboard />} />
          <Route
            path="/commissioner/lineup-rules"
            element={<LineupRules />}
          />
          <Route
            path="/commissioner/manage-owners"
            element={<ManageOwners />}
          />
          <Route
            path="/commissioner/manage-waiver-rules"
            element={<ManageWaiverRules />}
          />
          <Route
            path="/commissioner/manage-trades"
            element={<ManageTrades />}
          />
          <Route
            path="/commissioner/manage-scoring-rules"
            element={<ManageScoringRules />}
          />
          <Route
            path="/commissioner/manage-divisions"
            element={<ManageDivisions />}
          />
          <Route
            path="/commissioner/keeper-rules"
            element={<KeeperRules />}
          />
          <Route
            path="/commissioner/ledger-statement"
            element={<LedgerStatement />}
          />
          <Route
            path="/waivers"
            element={
              <Waivers
                ownerId={activeOwnerId}
                username={username}
                leagueName={activeLeagueId}
              />
            }
          />
          <Route
            path="/waiver-rules"
            element={<WaiverRules leagueId={activeLeagueId} />}
          />
          <Route path="/bug-report" element={<BugReport />} />
          <Route path="/keepers" element={<Keepers />} />
          <Route path="/analytics" element={<AnalyticsDashboard />} />
          <Route path="/playoffs" element={<PlayoffBracket />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </Suspense>
      <LeagueAdvisor />
    </Layout>
  );
}

function App() {
  // --- 1.1 GLOBAL STATE ---
  const [token, setToken] = useState(null);
  const [activeLeagueId, setActiveLeagueId] = useState(
    localStorage.getItem('fantasyToken')
      ? localStorage.getItem('fantasyLeagueId')
      : null
  );
  const [activeOwnerId, setActiveOwnerId] = useState(
    localStorage.getItem('fantasyToken') ? localStorage.getItem('user_id') : null
  );
  const [username, setUsername] = useState('');
  const [layoutAlert, setLayoutAlert] = useState('');

  const [userInput, setUserInput] = useState('');
  const [passInput, setPassInput] = useState('');
  const [leagueInput, setLeagueInput] = useState('1'); // Default to "The Big Show" (league ID 1)
  const [error, setError] = useState('');

  // --- 1.2 LOGOUT (Stable reference for effects) ---
  const clearAuthState = useCallback(() => {
    setToken(null);
    setActiveOwnerId(null);
    setActiveLeagueId(null);
    setUsername('');
    setLayoutAlert('');
    localStorage.removeItem('fantasyToken');
    localStorage.removeItem('user_id');
    localStorage.removeItem('fantasyLeagueId');
  }, []);

  const handleLogout = useCallback(() => {
    apiClient.post('/auth/logout').catch(() => {});
    clearAuthState();
  }, [clearAuthState]);

  // --- 1.3 AUTH CHECK (The Guard) ---
  useEffect(() => {
    const storedToken = localStorage.getItem('fantasyToken');
    if (!storedToken) return;

    let authPromise;
    try {
      authPromise = apiClient.get('/auth/me');
    } catch {
      authPromise = null;
    }

    if (!authPromise || typeof authPromise.then !== 'function') return;

    authPromise
      .then((res) => {
        const payload = res?.data || {};
        setToken((current) => current || 'cookie-session');
        setActiveOwnerId(payload.user_id);
        setUsername(payload.username || '');
      })
      .catch(() => {
        clearAuthState();
      });
  }, [clearAuthState]);

  // Hydrate layout alert details from league settings when available.
  useEffect(() => {
    if (!activeLeagueId || !token) return;

    apiClient
      .get(`/leagues/${activeLeagueId}/settings`)
      .then((res) => {
        const data = res?.data || {};
        const parts = [];
        if (data.waiver_deadline) parts.push(`Waiver: ${data.waiver_deadline}`);
        if (data.trade_deadline) parts.push(`Trade: ${data.trade_deadline}`);
        setLayoutAlert(parts.join(' | '));
      })
      .catch(() => setLayoutAlert(''));
  }, [activeLeagueId, token]);

  // --- 1.5 LOGIN HANDLER ---
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

      const { owner_id } = response.data;

      localStorage.setItem('fantasyToken', 'cookie-session');
      localStorage.setItem('user_id', owner_id);
      localStorage.setItem('fantasyLeagueId', leagueInput); // Use user-provided league ID

      setToken('cookie-session');
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

  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthenticatedShell
          username={username}
          activeLeagueId={activeLeagueId}
          handleLogout={handleLogout}
          layoutAlert={layoutAlert}
          token={token}
          activeOwnerId={activeOwnerId}
        />
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
