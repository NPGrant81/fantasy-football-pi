import { useEffect, useState, useCallback, useMemo } from 'react';
import apiClient from '@api/client';
import { useDraftTimer } from '@hooks/useDraftTimer';
import { getOwnerStats, ROSTER_SIZE } from '@utils';
import { FiBarChart2, FiX } from 'react-icons/fi';
import {
  AuctionBlock,
  SessionHeader,
  DraftHistoryFeed,
} from '@components/draft';
import DraftBoardGrid from '@components/draft/DraftBoardGrid';
import BestAvailableList from '@components/draft/BestAvailableList';
import PlayerIdentityCard from '@components/player/PlayerIdentityCard';
import {
  modalCloseButton,
  modalOverlay,
  modalSurface,
  modalTitle,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '@utils/uiStandards';

export default function DraftBoard({ token, activeOwnerId, activeLeagueId }) {
  // --- 1.1 STATE MANAGEMENT ---
  const [showBestSidebar, setShowBestSidebar] = useState(false);
  const [owners, setOwners] = useState([]);
  const [players, setPlayers] = useState([]);
  const [winnerId, setWinnerId] = useState(activeOwnerId);
  const [draftYear, setDraftYear] = useState(() => new Date().getFullYear());
  const [budgetMap, setBudgetMap] = useState({});
  const [leagueName, setLeagueName] = useState('');
  const [isCommissioner, setIsCommissioner] = useState(false);
  const [username, setUsername] = useState('');
  const [isPaused, setIsPaused] = useState(false);
  const [history, setHistory] = useState([]);
  const [playerName, setPlayerName] = useState('');
  const [bidAmount, setBidAmount] = useState(1);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [posFilter, setPosFilter] = useState('ALL');
  const [showPlayerPerformance, setShowPlayerPerformance] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [playerPerformance, setPlayerPerformance] = useState(null);
  const [playerPerformanceLoading, setPlayerPerformanceLoading] =
    useState(false);

  const sessionId = useMemo(() => {
    if (activeLeagueId && draftYear) {
      return `LEAGUE_${activeLeagueId}_YEAR_${draftYear}`;
    }
    return `TEST_${new Date().toISOString().slice(0, 10)}`;
  }, [activeLeagueId, draftYear]);

  const effectiveWinnerId = useMemo(() => {
    if (owners.length === 0) return winnerId;
    return owners.some((owner) => owner.id === winnerId)
      ? winnerId
      : owners[0].id;
  }, [owners, winnerId]);

  // highlight column based on username (falls back to prop)
  const highlightOwnerId = useMemo(() => {
    if (owners.length > 0 && username) {
      const mine = owners.find((o) => o.username === username);
      if (mine) return mine.id;
    }
    return activeOwnerId;
  }, [owners, username, activeOwnerId]);

  // --- 1.2 THE ENGINE (Logic Actions) ---

  const fetchHistory = useCallback(() => {
    apiClient
      .get(`/draft/history?session_id=${sessionId}`)
      .then((res) => setHistory(res.data))
      .catch(() => console.log('No history yet'));
  }, [sessionId]);

  // 1.2.1 THE DRAFT ACTION
  // We define this first, but we remove the 'reset' dependency.
  // The timer will now handle its own reset when handleDraft is triggered by the clock.
  const handleDraft = useCallback(
    async (forced = false) => {
      console.log('handleDraft invoked, forced=', forced);
      if (forced) {
        console.log('timer expired, forcing draft');
      }
      if (!effectiveWinnerId || !playerName) return;
      const foundPlayer = players.find(
        (p) => p.name.toLowerCase() === playerName.toLowerCase()
      );
      if (!foundPlayer || history.some((h) => h.player_id === foundPlayer.id))
        return;

      const payload = {
        owner_id: effectiveWinnerId,
        player_id: foundPlayer.id,
        amount: bidAmount,
        session_id: sessionId,
        year: draftYear,
      };

      try {
        await apiClient.post('/draft/pick', payload);
        setPlayerName('');
        setBidAmount(1);
        fetchHistory();
        // NOTE: We don't call reset() here anymore because the hook triggers it
        // when the button is clicked or time is up.
      } catch (err) {
        alert('Draft failed! ' + (err.response?.data?.detail || 'Error'));
      }
    },
    [
      effectiveWinnerId,
      playerName,
      players,
      history,
      bidAmount,
      sessionId,
      draftYear,
      fetchHistory,
    ]
  );
  // 1.2.2 THE TIMER HOOK
  // Now that handleDraft is defined, we pass it in.
  const {
    timeLeft,
    start,
    reset,
    isActive: isTimerRunning,
  } = useDraftTimer(10, () => handleDraft(true)); // call with forced flag on expiry

  // --- 1.3 SEARCH & POLL ---

  const handleSearchChange = async (e) => {
    const val = e.target.value;
    setPlayerName(val);
    if (val.length > 1) {
      try {
        const res = await apiClient.get(
          `/players/search?q=${val}&pos=${posFilter}`
        );
        const draftedIds = new Set(history.map((h) => h.player_id));
        const filtered = res.data.filter((p) => !draftedIds.has(p.id));
        setSuggestions(filtered.slice(0, 8));
        setShowSuggestions(true);
      } catch (err) {
        console.error(err);
      }
    } else {
      setShowSuggestions(false);
    }
  };

  useEffect(() => {
    if (token && activeLeagueId) {
      const leagueIdInt = parseInt(activeLeagueId, 10);
      if (isNaN(leagueIdInt)) {
        console.error('Invalid league_id:', activeLeagueId);
        return undefined;
      }
      apiClient
        .get(`/leagues/owners?league_id=${leagueIdInt}`)
        .then((res) => setOwners(res.data))
        .catch(() => setOwners([]));
      apiClient.get('/players/').then((res) => setPlayers(res.data));
      fetchHistory();
      // Fetch league name and user info
      apiClient
        .get(`/leagues/${activeLeagueId}`)
        .then((res) => setLeagueName(res.data.name))
        .catch(() => setLeagueName('League'));
      apiClient
        .get('/auth/me')
        .then((res) => {
          setIsCommissioner(res.data.is_commissioner);
          setUsername(res.data.username);
        })
        .catch(() => {
          setIsCommissioner(false);
          setUsername('');
        });
      apiClient
        .get(`/leagues/${activeLeagueId}/settings`)
        .then((res) => {
          if (res.data?.draft_year) {
            setDraftYear(res.data.draft_year);
          }
        })
        .catch(() => {});
      const interval = setInterval(fetchHistory, 3000);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [token, activeLeagueId, fetchHistory]);

  const handlePause = useCallback(() => {
    setIsPaused((p) => !p);
    // TODO: notify backend or disable interactions
  }, []);

  useEffect(() => {
    if (!activeLeagueId || !draftYear) return;
    apiClient
      .get(`/leagues/${activeLeagueId}/budgets?year=${draftYear}`)
      .then((res) => {
        const rows = res.data || [];
        const map = {};
        rows.forEach((row) => {
          if (row.total_budget != null) {
            map[row.owner_id] = row.total_budget;
          }
        });
        setBudgetMap(map);
      })
      .catch(() => {
        setBudgetMap({});
      });
  }, [activeLeagueId, draftYear]);

  // --- 1.4 DERIVED CALCULATIONS ---
  const currentNominatorId = useMemo(() => {
    if (owners.length === 0) return null;
    return [...owners].sort((a, b) => a.id - b.id)[
      history.length % owners.length
    ].id;
  }, [owners, history.length]);

  const activeStats = useMemo(() => {
    return effectiveWinnerId
      ? getOwnerStats(effectiveWinnerId, history, budgetMap)
      : null;
  }, [effectiveWinnerId, history, budgetMap]);

  // --- 2.1 RENDER (content only; header provided by Layout) ---
  // helper used by AuctionBlock to choose a suggestion
  const selectSuggestion = useCallback((p) => {
    setPlayerName(p.name);
    setShowSuggestions(false);
  }, []);

  const openPlayerPerformance = useCallback(
    async (draftedPlayer) => {
      const playerId = Number(draftedPlayer?.player_id || draftedPlayer?.id);
      if (!playerId) return;

      const fullPlayer = players.find((player) => player.id === playerId);
      const selected = {
        ...draftedPlayer,
        ...(fullPlayer || {}),
        id: playerId,
        player_id: playerId,
        name:
          fullPlayer?.name ||
          draftedPlayer?.player_name ||
          draftedPlayer?.name ||
          'Unknown Player',
        position:
          draftedPlayer?.position || fullPlayer?.position || draftedPlayer?.pos,
        nfl_team: fullPlayer?.nfl_team || draftedPlayer?.nfl_team,
      };

      setSelectedPlayer(selected);
      setShowPlayerPerformance(true);
      setPlayerPerformanceLoading(true);

      try {
        const res = await apiClient.get(
          `/players/${playerId}/season-details?season=${draftYear}`
        );
        setPlayerPerformance(res.data);
      } catch (error) {
        console.error('Failed to load player performance', error);
        setPlayerPerformance(null);
      } finally {
        setPlayerPerformanceLoading(false);
      }
    },
    [players, draftYear]
  );

  return (
    <div className={`${pageShell} overflow-hidden`}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Draft Board</h1>
        <p className={pageSubtitle}>
          {leagueName ? `${leagueName} • ` : ''}Live auction control room.
        </p>
      </div>

      {/* banner rendered below via SessionHeader */}
      <SessionHeader
        sessionId={sessionId}
        rosterSize={ROSTER_SIZE}
        leagueName={leagueName}
        username={username}
        isCommissioner={isCommissioner}
        isPaused={isPaused}
        onPause={handlePause}
      />

      {/* auction controls top bar */}
      <div className="w-full">
        <div className="flex flex-wrap items-end justify-start p-2 bg-slate-900/60">
          {/* auction controls panel handles its own internal alignment */}
          <AuctionBlock
            playerName={playerName}
            handleSearchChange={handleSearchChange}
            suggestions={suggestions}
            showSuggestions={showSuggestions}
            selectSuggestion={selectSuggestion}
            posFilter={posFilter}
            setPosFilter={setPosFilter}
            winnerId={winnerId}
            setWinnerId={setWinnerId}
            owners={owners}
            activeStats={activeStats}
            bidAmount={bidAmount}
            setBidAmount={setBidAmount}
            handleDraft={handleDraft}
            timeLeft={timeLeft}
            isTimerRunning={isTimerRunning}
            reset={reset}
            start={start}
            nominatorId={currentNominatorId}
            isCommissioner={isCommissioner}
            showBestSidebar={showBestSidebar}
            toggleSidebar={(v) => setShowBestSidebar(v)}
          />
        </div>
      </div>

      {/* ticker area */}
      <DraftHistoryFeed history={history} owners={owners} />

      <main className="flex-1 grid grid-cols-12 h-[70vh] md:h-screen gap-0 overflow-hidden z-0">
        <section
          className={`overflow-x-auto border-r border-slate-800 custom-scrollbar ${showBestSidebar ? 'col-span-12 md:col-span-9' : 'col-span-12'}`}
        >
          <DraftBoardGrid
            teams={owners}
            history={history}
            rosterLimit={ROSTER_SIZE}
            highlightOwnerId={highlightOwnerId}
            onPlayerClick={openPlayerPerformance}
          />
        </section>

        <aside
          className={`${showBestSidebar ? 'block' : 'hidden'} col-span-12 md:col-span-3 max-w-[260px] flex flex-col bg-slate-900/50 p-4 gap-4 overflow-y-auto`}
        >
          <BestAvailableList
            open={showBestSidebar}
            onToggle={() => setShowBestSidebar(false)}
            players={players
              .filter((p) => !history.some((h) => h.player_id === p.id))
              .sort((a, b) => a.rank - b.rank)
              .slice(0, 50)}
          />
        </aside>
      </main>

      <footer className="bg-slate-900 px-4 py-1 flex justify-between text-[10px] text-slate-500 border-t border-slate-800">
        <span>SESSION ID: {sessionId}</span>
        <span className="text-green-500 font-mono">SERVER STATUS: ONLINE</span>
      </footer>

      {showPlayerPerformance && (
        <div className={modalOverlay}>
          <div className={`${modalSurface} max-w-4xl p-6`}>
            <div className="mb-5 flex items-center justify-between">
              <h3
                className={`${modalTitle} mb-0 w-full justify-center text-center`}
              >
                Season Performance
              </h3>
              <button
                onClick={() => setShowPlayerPerformance(false)}
                className={modalCloseButton}
              >
                <FiX />
              </button>
            </div>

            {playerPerformanceLoading ? (
              <div className="py-10 text-center text-slate-400 animate-pulse">
                Loading season details...
              </div>
            ) : playerPerformance ? (
              <>
                <PlayerIdentityCard
                  playerName={
                    playerPerformance.player_name || selectedPlayer?.name || ''
                  }
                  position={
                    playerPerformance.position || selectedPlayer?.position || ''
                  }
                  nflTeam={
                    playerPerformance.nfl_team || selectedPlayer?.nfl_team || ''
                  }
                  headshotUrl={playerPerformance.headshot_url || ''}
                />

                <div className="grid grid-cols-2 gap-3 mb-5 md:grid-cols-4">
                  <div className="rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                    <div className="text-[10px] uppercase text-slate-500">
                      Games
                    </div>
                    <div className="text-xl font-black text-slate-900 dark:text-white">
                      {playerPerformance.games_played}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                    <div className="text-[10px] uppercase text-slate-500">
                      Total Pts
                    </div>
                    <div className="text-xl font-black text-blue-400">
                      {Number(
                        playerPerformance.total_fantasy_points || 0
                      ).toFixed(2)}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                    <div className="text-[10px] uppercase text-slate-500">
                      Avg / Game
                    </div>
                    <div className="text-xl font-black text-slate-900 dark:text-white">
                      {Number(
                        playerPerformance.average_fantasy_points || 0
                      ).toFixed(2)}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                    <div className="text-[10px] uppercase text-slate-500">
                      Best Week
                    </div>
                    <div className="text-xl font-black text-green-400">
                      {Number(playerPerformance.best_week_points || 0).toFixed(
                        2
                      )}
                    </div>
                  </div>
                </div>

                <div className="overflow-hidden rounded-xl border border-slate-300 dark:border-slate-700">
                  <div className="flex items-center gap-2 bg-slate-100 px-4 py-2 text-xs font-bold uppercase tracking-wider text-slate-600 dark:bg-slate-950 dark:text-slate-400">
                    <FiBarChart2 /> Weekly Breakdown
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    {(playerPerformance.weekly || []).length === 0 ? (
                      <div className="p-6 text-center text-slate-500">
                        No weekly performance data yet for this season.
                      </div>
                    ) : (
                      <table className="w-full text-left text-sm text-slate-700 dark:text-slate-300">
                        <thead className="bg-slate-100 text-xs uppercase text-slate-500 dark:bg-slate-900">
                          <tr>
                            <th className="px-4 py-2">Week</th>
                            <th className="px-4 py-2 text-right">
                              Fantasy Pts
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {playerPerformance.weekly.map((row) => (
                            <tr
                              key={row.week}
                              className="border-t border-slate-300 dark:border-slate-800"
                            >
                              <td className="px-4 py-2">Week {row.week}</td>
                              <td className="px-4 py-2 text-right font-mono text-blue-400">
                                {Number(row.fantasy_points || 0).toFixed(2)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="py-10 text-center text-slate-500">
                No season details available.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
