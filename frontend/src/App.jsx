import { useState, useEffect, useCallback, useRef, lazy, Suspense } from 'react';
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
import BrandMark from './components/BrandMark';
import LeagueSelector from './components/LeagueSelector';
import LeagueAdvisor from './components/LeagueAdvisor';
import { LoadingState } from '@components/common/AsyncState';
import { BRAND_NAME } from './constants/branding';
import { ThemeProvider } from './context/ThemeContext';
import { LeagueContext } from './context/LeagueContext';
import { emitVisitEvent } from './services/visitLogger';

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
const HistoryOwnerMappingUtility = lazy(
  () => import('./pages/commissioner/HistoryOwnerMappingUtility')
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
const LeagueHistory = lazy(() => import('./pages/history/LeagueHistory'));

function TeamRoute({ fallbackOwnerId }) {
  const { ownerId } = useParams();
  return <YourLockerRoom activeOwnerId={ownerId || fallbackOwnerId} />;
}

function RequireCommissioner({ isCommissioner, children }) {
  if (!isCommissioner) {
    return <Navigate to="/team" replace />;
  }
  return children;
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
  if (pathname === '/commissioner/history-owner-mapping') return 'Historical Owner Mapping';
  if (pathname === '/commissioner/keeper-rules') return 'Keeper Rules';
  if (pathname === '/commissioner/ledger-statement') return 'Ledger Statement';
  if (pathname === '/waivers') return 'Waiver Wire';
  if (pathname === '/waiver-rules') return 'Waiver Rules';
  if (pathname === '/bug-report') return 'Bug Report';
  if (pathname === '/keepers') return 'Manage Keepers';
  if (pathname === '/analytics') return 'League Analytics';
  if (pathname === '/playoffs') return 'Playoff Bracket';
  if (pathname === '/league-history') return 'League History';
  if (pathname === '/league-history/historical-analytics') return 'League History · Historical Analytics';
  if (pathname === '/league-history/champions') return 'League History · League Champions';
  if (pathname === '/league-history/awards') return 'League History · Awards';
  if (pathname === '/league-history/franchise-records') return 'League History · Franchise Records';
  if (pathname === '/league-history/player-records') return 'League History · Player Records';
  if (pathname === '/league-history/match-records') return 'League History · Match Records';
  if (pathname === '/league-history/all-time-series-records') return 'League History · All-Time Series Records';
  if (pathname === '/league-history/season-records') return 'League History · Season Records';
  if (pathname === '/league-history/career-records') return 'League History · Career Records';
  if (pathname === '/league-history/record-streaks') return 'League History · Record Streaks';
  return BRAND_NAME;
}

function AuthenticatedShell({
  username,
  activeLeagueId,
  handleLogout,
  layoutAlert,
  token,
  activeOwnerId,
  isCommissioner,
  isSuperuser,
  onLeagueSwitch,
}) {
  const location = useLocation();
  const hasLoggedInitialRoute = useRef(false);
  const headerTitle = resolveLayoutPageTitle(location.pathname);

  useEffect(() => {
    document.title = headerTitle ? `${headerTitle} | ${BRAND_NAME}` : BRAND_NAME;
  }, [headerTitle]);

  useEffect(() => {
    if (!hasLoggedInitialRoute.current) {
      hasLoggedInitialRoute.current = true;
      return;
    }
    emitVisitEvent(location.pathname, activeOwnerId ? Number(activeOwnerId) : null);
  }, [location.pathname, activeOwnerId]);
  return (
    <Layout
      username={username}
      leagueId={activeLeagueId}
      alert={layoutAlert}
      onLogout={handleLogout}
      pageTitle={headerTitle}
      isCommissioner={isCommissioner}
      isSuperuser={isSuperuser}
      onLeagueSwitch={onLeagueSwitch}
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
          <Route
            path="/commissioner"
            element={
              <RequireCommissioner isCommissioner={isCommissioner}>
                <CommissionerDashboard />
              </RequireCommissioner>
            }
          />
          <Route
            path="/commissioner/lineup-rules"
            element={
              <RequireCommissioner isCommissioner={isCommissioner}>
                <LineupRules />
              </RequireCommissioner>
            }
          />
          <Route
            path="/commissioner/manage-owners"
            element={
              <RequireCommissioner isCommissioner={isCommissioner}>
                <ManageOwners />
              </RequireCommissioner>
            }
          />
          <Route
            path="/commissioner/manage-waiver-rules"
            element={
              <RequireCommissioner isCommissioner={isCommissioner}>
                <ManageWaiverRules />
              </RequireCommissioner>
            }
          />
          <Route
            path="/commissioner/manage-trades"
            element={
              <RequireCommissioner isCommissioner={isCommissioner}>
                <ManageTrades />
              </RequireCommissioner>
            }
          />
          <Route
            path="/commissioner/manage-scoring-rules"
            element={
              <RequireCommissioner isCommissioner={isCommissioner}>
                <ManageScoringRules />
              </RequireCommissioner>
            }
          />
          <Route
            path="/commissioner/manage-divisions"
            element={
              <RequireCommissioner isCommissioner={isCommissioner}>
                <ManageDivisions />
              </RequireCommissioner>
            }
          />
          <Route
            path="/commissioner/history-owner-mapping"
            element={
              <RequireCommissioner isCommissioner={isCommissioner}>
                <HistoryOwnerMappingUtility />
              </RequireCommissioner>
            }
          />
          <Route
            path="/commissioner/keeper-rules"
            element={
              <RequireCommissioner isCommissioner={isCommissioner}>
                <KeeperRules />
              </RequireCommissioner>
            }
          />
          <Route
            path="/commissioner/ledger-statement"
            element={
              <RequireCommissioner isCommissioner={isCommissioner}>
                <LedgerStatement />
              </RequireCommissioner>
            }
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
          <Route
            path="/league-history"
            element={<Navigate to="/league-history/historical-analytics" replace />}
          />
          <Route
            path="/league-history/historical-analytics"
            element={<LeagueHistory sectionKey="historical-analytics" />}
          />
          <Route
            path="/league-history/champions"
            element={<LeagueHistory sectionKey="champions" />}
          />
          <Route
            path="/league-history/awards"
            element={<LeagueHistory sectionKey="awards" />}
          />
          <Route
            path="/league-history/franchise-records"
            element={<LeagueHistory sectionKey="franchise-records" />}
          />
          <Route
            path="/league-history/player-records"
            element={<LeagueHistory sectionKey="player-records" />}
          />
          <Route
            path="/league-history/match-records"
            element={<LeagueHistory sectionKey="match-records" />}
          />
          <Route
            path="/league-history/all-time-series-records"
            element={<LeagueHistory sectionKey="all-time-series-records" />}
          />
          <Route
            path="/league-history/season-records"
            element={<LeagueHistory sectionKey="season-records" />}
          />
          <Route
            path="/league-history/career-records"
            element={<LeagueHistory sectionKey="career-records" />}
          />
          <Route
            path="/league-history/record-streaks"
            element={<LeagueHistory sectionKey="record-streaks" />}
          />
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
  const [isCommissioner, setIsCommissioner] = useState(false);
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [layoutAlert, setLayoutAlert] = useState('');

  const [userInput, setUserInput] = useState('');
  const [passInput, setPassInput] = useState('');
  const [leagueInput, setLeagueInput] = useState('1'); // Default to "The Big Show" (league ID 1)
  const [error, setError] = useState('');
  const authCheckIdRef = useRef(0);
  const isLoggingOutRef = useRef(false);
  const pendingLogoutRequestRef = useRef(null);

  useEffect(() => {
    const initialPath =
      typeof window !== 'undefined' && window.location?.pathname
        ? window.location.pathname
        : '/';
    const storedUserId = localStorage.getItem('user_id');
    emitVisitEvent(initialPath, storedUserId ? Number(storedUserId) : null);
  }, []);

  // --- 1.2 LOGOUT (Stable reference for effects) ---
  const clearAuthState = useCallback(() => {
    isLoggingOutRef.current = true;
    setToken(null);
    setActiveOwnerId(null);
    setActiveLeagueId(null);
    setUsername('');
    setIsCommissioner(false);
    setIsSuperuser(false);
    setLayoutAlert('');
    localStorage.removeItem('fantasyToken');
    localStorage.removeItem('user_id');
    localStorage.removeItem('fantasyLeagueId');
  }, []);

  const handleLeagueSwitch = useCallback(() => {
    localStorage.removeItem('fantasyLeagueId');
    setActiveLeagueId(null);
  }, []);

  const handleLogout = useCallback(() => {
    isLoggingOutRef.current = true;
    authCheckIdRef.current += 1;
    // Clear local state immediately so the UI responds at once rather than
    // waiting up to 5 s for the backend call to resolve / time out.
    clearAuthState();
    // Fire backend logout in the background to clear server-side cookies.
    // Failures are non-critical — local state is already cleared above.
    // Deduplicate: if a logout is already in flight, reuse it; don't start a new one.
    if (!pendingLogoutRequestRef.current) {
      const logoutRequest = apiClient
        .post('/auth/logout', null, { timeout: 5000 })
        .catch(() => {
          // intentionally swallowed
        })
        .finally(() => {
          if (pendingLogoutRequestRef.current === logoutRequest) {
            pendingLogoutRequestRef.current = null;
          }
        });

      pendingLogoutRequestRef.current = logoutRequest;
    }
  }, [clearAuthState]);

  // --- 1.3 AUTH CHECK (The Guard) ---
  useEffect(() => {
    const storedToken = localStorage.getItem('fantasyToken');
    if (!storedToken || isLoggingOutRef.current) return;

    const authCheckId = ++authCheckIdRef.current;

    let authPromise;
    try {
      authPromise = apiClient.get('/auth/me');
    } catch {
      authPromise = null;
    }

    if (!authPromise || typeof authPromise.then !== 'function') return;

    authPromise
      .then((res) => {
        if (authCheckId !== authCheckIdRef.current || isLoggingOutRef.current) {
          return;
        }
        const payload = res?.data || {};
        setToken((current) => current || 'cookie-session');
        const resolvedLeagueId =
          payload.league_id === null || payload.league_id === undefined
            ? null
            : String(payload.league_id);
        setActiveOwnerId(payload.user_id);
        // Prefer the league already stored in localStorage (selected at login)
        // over the user record's default league_id from the server, so switching
        // leagues persists across page refreshes.
        const storedLeagueId = localStorage.getItem('fantasyLeagueId');
        setActiveLeagueId(storedLeagueId || resolvedLeagueId);
        setUsername(payload.username || '');
        setIsCommissioner(Boolean(payload.is_commissioner));
        setIsSuperuser(Boolean(payload.is_superuser));
      })
      .catch(() => {
        if (authCheckId !== authCheckIdRef.current || isLoggingOutRef.current) {
          return;
        }
        clearAuthState();
      });
  }, [clearAuthState]);

  useEffect(() => {
    if (!token) {
      localStorage.removeItem('fantasyLeagueId');
      return;
    }
    if (activeLeagueId === null || activeLeagueId === undefined || activeLeagueId === '') {
      localStorage.removeItem('fantasyLeagueId');
      return;
    }
    localStorage.setItem('fantasyLeagueId', String(activeLeagueId));
  }, [activeLeagueId, token]);

  useEffect(() => {
    if (token || !isLoggingOutRef.current) return;
    localStorage.removeItem('fantasyToken');
    localStorage.removeItem('user_id');
    localStorage.removeItem('fantasyLeagueId');
  }, [token]);

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

  useEffect(() => {
    if (!token) {
      document.title = `${BRAND_NAME} Login`;
    }
  }, [token]);

  // --- 1.5 LOGIN HANDLER ---
  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');

    // Ensure an earlier logout response cannot clear fresh login cookies.
    // Cap the wait time so a slow/unreachable backend doesn't block login (logout is non-critical).
    if (pendingLogoutRequestRef.current) {
      const logoutPromise = pendingLogoutRequestRef.current;
      await Promise.race([
        logoutPromise,
        new Promise((resolve) => setTimeout(resolve, 500)),
      ]);
    }

    const formData = new URLSearchParams();
    formData.append('username', userInput);
    formData.append('password', passInput);

    try {
      // UPDATED: Standard OAuth2 tokenUrl is now under /auth
      const response = await apiClient.post('/auth/token', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      const { owner_id, league_id, is_commissioner, is_superuser } = response.data;
      const resolvedLeagueId =
        league_id === null || league_id === undefined ? null : String(league_id);
      isLoggingOutRef.current = false;

      localStorage.setItem('fantasyToken', 'cookie-session');
      localStorage.setItem('user_id', owner_id);
      if (resolvedLeagueId) {
        localStorage.setItem('fantasyLeagueId', resolvedLeagueId);
      } else {
        localStorage.removeItem('fantasyLeagueId');
      }

      setToken('cookie-session');
      setActiveOwnerId(owner_id);
      setActiveLeagueId(resolvedLeagueId);
      setIsCommissioner(Boolean(is_commissioner));
      setIsSuperuser(Boolean(is_superuser));
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
            <BrandMark
              containerClassName="flex flex-col items-center"
              imageClassName="w-16 h-16 mb-2"
              textClassName="text-3xl font-black text-center text-yellow-500 tracking-tighter"
              text={`${BRAND_NAME} Login`}
              textTag="h2"
            />
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
    <LeagueContext.Provider value={{ activeLeagueId }}>
      <ThemeProvider>
        <BrowserRouter>
          <AuthenticatedShell
            username={username}
            activeLeagueId={activeLeagueId}
            handleLogout={handleLogout}
            layoutAlert={layoutAlert}
            token={token}
            activeOwnerId={activeOwnerId}
            isCommissioner={isCommissioner}
            isCommissioner={isCommissioner}
            isCommissioner={isCommissioner}
            isSuperuser={isSuperuser}
            onLeagueSwitch={handleLeagueSwitch}
          />
        </BrowserRouter>
      </ThemeProvider>
    </LeagueContext.Provider>
  );
}

export default App;
