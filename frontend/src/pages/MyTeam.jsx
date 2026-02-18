import { useEffect, useState, useMemo, useCallback } from 'react';
import { FiUser, FiAlertTriangle, FiTrendingUp, FiRepeat, FiBell, FiPlus, FiList } from 'react-icons/fi';
import { Link } from 'react-router-dom';
// --- Commissioner Modal Imports ---
import ScoringRulesModal from '../components/commissioner/ScoringRulesModal';
import OwnerManagementModal from '../components/commissioner/OwnerManagementModal';
import WaiverWireRulesModal from '../components/commissioner/WaiverWireRulesModal';
import TradeRulesModal from '../components/commissioner/TradeRulesModal';


// Professional Imports
import apiClient from '@api/client';
import LeagueAdvisor from '../components/LeagueAdvisor';

// --- 1.1 CONSTANTS & HELPERS (Outside Render) ---
const POS_RANK = { QB: 1, RB: 2, WR: 3, TE: 4, DEF: 5, K: 6 };

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
);

const RosterTable = ({
  title,
  players,
  titleColor,
  emptyMsg,
  totalYTD,
  totalProj,
  sortConfig,
  handleSort,
}) => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl mb-8 animate-fade-in-up">
    <div
      className={`p-4 border-b border-slate-800 flex justify-between items-center ${titleColor} bg-slate-950/50`}
    >
      <h3 className="font-bold uppercase tracking-wider flex items-center gap-2">
        {title}{' '}
        <span className="text-xs opacity-60 bg-black/30 px-2 py-1 rounded">
          {players.length}
        </span>
      </h3>

      {title === 'Active Lineup' && (
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
            <th
              className="px-6 py-3 hover:text-white transition"
              onClick={() => handleSort('position_rank')}
            >
              Pos{' '}
              {sortConfig.key === 'position_rank' &&
                (sortConfig.direction === 'asc' ? '↓' : '↑')}
            </th>
            <th
              className="px-6 py-3 hover:text-white transition"
              onClick={() => handleSort('name')}
            >
              Player{' '}
              {sortConfig.key === 'name' &&
                (sortConfig.direction === 'asc' ? '↓' : '↑')}
            </th>
            <th
              className="px-6 py-3 hover:text-white transition"
              onClick={() => handleSort('bye_week')}
            >
              Bye{' '}
              {sortConfig.key === 'bye_week' &&
                (sortConfig.direction === 'asc' ? '↓' : '↑')}
            </th>
            <th
              className="px-6 py-3 text-right hover:text-white transition"
              onClick={() => handleSort('ytd_score')}
            >
              YTD{' '}
              {sortConfig.key === 'ytd_score' &&
                (sortConfig.direction === 'asc' ? '↓' : '↑')}
            </th>
            <th
              className="px-6 py-3 text-right hover:text-white transition"
              onClick={() => handleSort('proj_score')}
            >
              Proj{' '}
              {sortConfig.key === 'proj_score' &&
                (sortConfig.direction === 'asc' ? '↓' : '↑')}
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {players.map((p) => (
            <tr
              key={p.player_id}
              className="hover:bg-slate-800/50 transition duration-150"
            >
              <td className="px-6 py-4">
                <span
                  className={`px-2 py-1 rounded text-xs font-bold border ${
                    p.position === 'QB'
                      ? 'text-red-300 border-red-900 bg-red-900/20'
                      : p.position === 'RB'
                        ? 'text-green-300 border-green-900 bg-green-900/20'
                        : p.position === 'WR'
                          ? 'text-blue-300 border-blue-900 bg-blue-900/20'
                          : p.position === 'TE'
                            ? 'text-orange-300 border-orange-900 bg-orange-900/20'
                            : 'text-slate-300 border-slate-600'
                  }`}
                >
                  {p.position}
                </span>
              </td>
              <td className="px-6 py-4 font-bold text-white">
                {p.name}
                <div className="text-[10px] font-normal text-slate-500">
                  {p.nfl_team}
                </div>
              </td>
              <td className="px-6 py-4">
                {p.bye_week === 8 ? (
                  <span className="text-red-500 font-bold flex gap-1 items-center">
                    <FiAlertTriangle /> W8
                  </span>
                ) : (
                  `Week ${p.bye_week}`
                )}
              </td>
              <td className="px-6 py-4 text-right font-mono">{p.ytd_score}</td>
              <td className="px-6 py-4 text-right font-mono text-blue-400 font-bold">
                {p.proj_score}
              </td>
            </tr>
          ))}
          {players.length === 0 && (
            <tr>
              <td
                colSpan="6"
                className="text-center py-8 text-slate-600 italic"
              >
                {emptyMsg}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  </div>
);

export default function MyTeam({ activeOwnerId }) {
  // --- 0.1 Commissioner Modal State ---
  const [showScoring, setShowScoring] = useState(false);
  const [showOwners, setShowOwners] = useState(false);
  const [showWaivers, setShowWaivers] = useState(false);
  const [showTrades, setShowTrades] = useState(false);
  // --- USER/LEAGUE CONTEXT ---
  const [userInfo, setUserInfo] = useState({ username: '', leagueName: '', leagueId: null, is_commissioner: false });
  const [scoringRules, setScoringRules] = useState([]);
  const [summary, setSummary] = useState(null);
  useEffect(() => {
    async function fetchUserLeague() {
      try {
        const userRes = await apiClient.get('/auth/me');
        let leagueName = '';
        let leagueId = userRes.data.league_id;
        let is_commissioner = userRes.data.is_commissioner;
        if (leagueId) {
          const leagueRes = await apiClient.get(`/leagues/${leagueId}`);
          leagueName = leagueRes.data.name;
          // Fetch scoring rules
          const settingsRes = await apiClient.get(`/leagues/${leagueId}/settings`);
          setScoringRules(settingsRes.data.scoring_rules || []);
        }
        setUserInfo({ username: userRes.data.username, leagueName, leagueId, is_commissioner });
        // Fetch dashboard summary for locker room
        if (userRes.data.user_id) {
          const dashRes = await apiClient.get(`/dashboard/${userRes.data.user_id}`);
          setSummary(dashRes.data);
        }
      } catch (err) {
        setUserInfo({ username: '', leagueName: '', leagueId: null, is_commissioner: false });
        setScoringRules([]);
        setSummary(null);
      }
    }
    fetchUserLeague();
  }, []);
  // --- 1.2 STATE MANAGEMENT ---
  const [teamData, setTeamData] = useState(null);
  const [rosterState, setRosterState] = useState([]);
  // FIX: Start loading as true to avoid sync setState inside useEffect
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortConfig, setSortConfig] = useState({
    key: 'proj_score',
    direction: 'desc',
  });
  const [activeFilter, setActiveFilter] = useState('ALL');

  // --- 1.3 DATA RETRIEVAL (The Engine) ---
  const fetchTeam = useCallback(() => {
    if (activeOwnerId) {
      // apiClient handles the Base URL and the token automatically via interceptors
      apiClient
        .get(`/team/${activeOwnerId}`)
        .then((res) => {
          setTeamData(res.data);
          const processedRoster = res.data.roster.map((p) => ({
            ...p,
            status: p.status || 'BENCH',
            position_rank: POS_RANK[p.position] || 99,
          }));
          setRosterState(processedRoster);
        })
        .catch((err) => console.error('Roster fetch failed', err))
        .finally(() => setLoading(false));
    }
  }, [activeOwnerId]);

  useEffect(() => {
    fetchTeam();
  }, [fetchTeam]);

  // --- 1.4 UTILITIES & DERIVED STATE ---
  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc')
      direction = 'desc';
    setSortConfig({ key, direction });
  };

  const processedPlayers = useMemo(() => {
    let players = [...rosterState];
    if (activeFilter !== 'ALL')
      players = players.filter((p) => p.position === activeFilter);
    if (searchTerm)
      players = players.filter((p) =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase())
      );

    players.sort((a, b) => {
      if (a[sortConfig.key] < b[sortConfig.key])
        return sortConfig.direction === 'asc' ? -1 : 1;
      if (a[sortConfig.key] > b[sortConfig.key])
        return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
    return players;
  }, [rosterState, searchTerm, sortConfig, activeFilter]);

  const starters = processedPlayers.filter((p) => p.status === 'STARTER');
  const bench = processedPlayers.filter((p) => p.status === 'BENCH');

  const totalYTD = starters
    .reduce((sum, p) => sum + (p.ytd_score || 0), 0)
    .toFixed(2);
  const totalProj = starters
    .reduce((sum, p) => sum + (p.proj_score || 0), 0)
    .toFixed(2);

  // --- 2.1 RENDER LOGIC (The View) ---

  if (loading)
    return (
      <div className="p-8 text-white animate-pulse">Loading Roster...</div>
    );
  if (!teamData)
    return <div className="text-red-500 p-8">Error loading team.</div>;

  // --- COMMISSIONER ACCESS BUTTON ---
  const commissionerControls = userInfo.is_commissioner && (
    <div className="flex flex-wrap gap-4 mb-6">
      <button onClick={() => setShowScoring(true)} className="bg-purple-700 hover:bg-purple-600 text-white px-4 py-2 rounded font-bold">Scoring Rules</button>
      <button onClick={() => setShowOwners(true)} className="bg-blue-700 hover:bg-blue-600 text-white px-4 py-2 rounded font-bold">Owner Management</button>
      <button onClick={() => setShowWaivers(true)} className="bg-green-700 hover:bg-green-600 text-white px-4 py-2 rounded font-bold">Waiver Wire Rules</button>
      <button onClick={() => setShowTrades(true)} className="bg-yellow-500 hover:bg-yellow-400 text-black px-4 py-2 rounded font-bold">Trade Rules</button>
    </div>
  );

  // --- LOCKER ROOM/ROSTER/WAIVER UI (from Dashboard.jsx) ---
  if (!summary)
    return (
      <div className="p-10 text-center animate-pulse text-slate-500 font-black uppercase">
        Loading your locker room...
      </div>
    );

  return (
    <div className="max-w-6xl mx-auto p-6 text-white min-h-screen">
      {commissionerControls}
      {/* Commissioner Modals */}
      <ScoringRulesModal open={showScoring} onClose={() => setShowScoring(false)} />
      <OwnerManagementModal open={showOwners} onClose={() => setShowOwners(false)} />
      <WaiverWireRulesModal open={showWaivers} onClose={() => setShowWaivers(false)} />
      <TradeRulesModal open={showTrades} onClose={() => setShowTrades(false)} />

      {/* HEADER SECTION */}
      <div className="flex justify-between items-end mb-12 border-b border-slate-800 pb-8">
        <div>
          <h1 className="text-6xl font-black italic uppercase tracking-tighter leading-none">
            Your Locker Room
          </h1>
          <p className="text-slate-400 mt-4 flex items-center gap-2">
            Current Standing:{' '}
            <span className="bg-purple-600 text-white px-3 py-1 rounded-lg font-black italic">
              #{summary.standing} Place
            </span>
          </p>
        </div>
        {/* STAT BOXES */}
        <div className="flex gap-4">
          <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl text-center min-w-[140px] shadow-2xl">
            <FiRepeat className="mx-auto mb-2 text-blue-400 text-2xl" />
            <div className="text-[10px] text-slate-500 uppercase font-black tracking-widest">
              Pending Trades
            </div>
            <div className="text-3xl font-black">{summary.pending_trades}</div>
          </div>
        </div>
      </div>

      {/* MAIN CONTENT GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        {/* LEFT COLUMN: ROSTER (8 Cols) */}
        <div className="lg:col-span-8 bg-slate-900/40 border border-slate-800 rounded-[2.5rem] p-8 backdrop-blur-sm">
          <h2 className="text-2xl font-black uppercase italic mb-8 flex items-center gap-3 text-slate-200">
            <FiTrendingUp className="text-green-500" /> Active Roster
          </h2>
          <div className="grid grid-cols-1 gap-3">
            {summary.roster.map((player) => (
              <div
                key={player.id}
                className="flex justify-between items-center p-5 bg-slate-950/50 border border-slate-800/50 rounded-2xl hover:border-blue-500/50 hover:bg-slate-900/50 transition-all duration-300 group"
              >
                <div className="flex items-center gap-5">
                  <span
                    className={`text-[10px] font-black px-3 py-1.5 rounded-md shadow-lg ${getPosColor(player.position)}`}
                  >
                    {normalizePos(player.position)}
                  </span>
                  <span className="font-bold text-xl tracking-tight group-hover:text-blue-400 transition-colors">
                    {player.name}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-slate-500 font-mono text-sm font-bold uppercase tracking-widest bg-slate-900 px-3 py-1 rounded-lg border border-slate-800">
                    {player.nfl_team}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT COLUMN: SIDEBAR (4 Cols) */}
        <div className="lg:col-span-4 space-y-8">
          {/* WAIVER QUICK ACTION */}
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-[2.5rem] shadow-2xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-green-500/5 blur-[80px] group-hover:bg-green-500/10 transition-all"></div>
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-black uppercase italic flex items-center gap-2 text-green-400 tracking-tighter text-xl">
                <FiList /> Waiver Wire
              </h3>
              <span className="text-[10px] bg-green-900/30 text-green-400 px-3 py-1 rounded-full border border-green-800/50 font-black">
                PRIORITY #4
              </span>
            </div>
            <p className="text-sm text-slate-400 mb-8 leading-relaxed">
              The wire is hot. Browse available free agents to fortify your
              lineup before the next window.
            </p>
            <Link
              to="/waivers"
              className="flex items-center justify-center gap-3 w-full py-4 bg-green-600 hover:bg-green-500 text-black rounded-2xl font-black uppercase tracking-widest transition shadow-[0_10px_20px_rgba(22,163,74,0.2)] active:scale-95"
            >
              <FiPlus className="text-xl" /> Find Players
            </Link>
          </div>

          {/* LEAGUE ALERTS */}
          <div className="bg-slate-900/80 border border-slate-800 p-8 rounded-[2.5rem]">
            <h3 className="font-black uppercase italic mb-6 flex items-center gap-2 text-slate-200 tracking-tighter text-xl">
              <FiBell className="text-blue-400" /> Sit-Rep
            </h3>
            <ul className="space-y-6">
              <li className="relative pl-6">
                <div className="absolute left-0 top-1 w-1 h-10 bg-purple-500 rounded-full"></div>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-1">
                  Waiver Deadline
                </p>
                <p className="text-white font-black text-lg">
                  2d 14h REMAINING
                </p>
              </li>
              <li className="relative pl-6 opacity-60">
                <div className="absolute left-0 top-1 w-1 h-10 bg-blue-500 rounded-full"></div>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-1">
                  Draft Status
                </p>
                <p className="text-white font-black text-lg tracking-tight uppercase">
                  Draft Finalized
                </p>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
