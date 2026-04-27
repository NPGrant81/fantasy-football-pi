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
import PageTemplate from '@components/layout/PageTemplate';
import DraftBoardGrid from '@components/draft/DraftBoardGrid';
import BestAvailableList from '@components/draft/BestAvailableList';
import { EmptyState, LoadingState } from '@components/common/AsyncState';
import PlayerIdentityCard from '@components/player/PlayerIdentityCard';
import {
  StandardTable,
  StandardTableHead,
  StandardTableRow,
} from '@components/table/TablePrimitives';
import {
  layerModal,
  modalCloseButton,
  modalOverlay,
  modalSurface,
  modalTitle,
  tableCell,
  tableCellNumeric,
} from '@utils/uiStandards';

const PLAYER_POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

const normalizeTeamCode = (value) => String(value || '').trim().toUpperCase();

const getLeagueActivePositions = (settings) => {
  const slots = settings?.starting_slots;
  if (!slots || Object.keys(slots).length === 0) {
    return PLAYER_POSITIONS;
  }

  const hasPositionConfig = PLAYER_POSITIONS.some(
    (position) => slots[`MAX_${position}`] != null || slots[position] != null
  );
  if (!hasPositionConfig) {
    return PLAYER_POSITIONS;
  }

  const activePositions = PLAYER_POSITIONS.filter((position) => {
    const rawValue =
      slots[`MAX_${position}`] ??
      slots[position] ??
      (position === 'DEF' ? 1 : 0);
    return Number(rawValue) > 0;
  });

  return activePositions.length > 0 ? activePositions : PLAYER_POSITIONS;
};

const isActiveDraftPlayer = (player) => {
  const team = normalizeTeamCode(player?.nfl_team);
  if (!team || team === 'FA') return false;

  const position = String(player?.position || player?.pos || '').toUpperCase();
  if (position === 'DEF') return true;

  return Boolean(player?.espn_id || player?.gsis_id);
};

export default function DraftBoard({ token, activeOwnerId, activeLeagueId }) {
  // --- 1.1 STATE MANAGEMENT ---
  const [showBestSidebar, setShowBestSidebar] = useState(false);
  const [owners, setOwners] = useState([]);
  const [players, setPlayers] = useState([]);
  const [winnerId, setWinnerId] = useState(activeOwnerId);
  const [draftYear, setDraftYear] = useState(() => new Date().getFullYear());
  const [rosterSize, setRosterSize] = useState(ROSTER_SIZE);
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
  const [activePositions, setActivePositions] = useState(PLAYER_POSITIONS);
  const [showPlayerPerformance, setShowPlayerPerformance] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [playerPerformance, setPlayerPerformance] = useState(null);
  const [playerPerformanceLoading, setPlayerPerformanceLoading] =
    useState(false);
  const [draftPopupData, setDraftPopupData] = useState(null);
  const [historicalRankings, setHistoricalRankings] = useState([]);

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

  const rankingByPlayerId = useMemo(() => {
    const index = new Map();
    historicalRankings.forEach((entry) => {
      index.set(entry.player_id, entry);
    });
    return index;
  }, [historicalRankings]);

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
      const winnerStats = getOwnerStats(
        effectiveWinnerId,
        history,
        budgetMap,
        undefined,
        rosterSize
      );
      if (bidAmount > winnerStats.maxBid) return;
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
        const draftedOwner = owners.find((owner) => owner.id === effectiveWinnerId);
        setDraftPopupData({
          playerName: foundPlayer.name,
          teamName: draftedOwner?.team_name || draftedOwner?.username || 'Unknown Team',
          amount: bidAmount,
        });
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
      owners,
      playerName,
      players,
      history,
      budgetMap,
      rosterSize,
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
  } = useDraftTimer(5, () => handleDraft(true)); // call with forced flag on expiry

  // --- 1.3 SEARCH & POLL ---

  const handleSearchChange = async (e) => {
    const val = e.target.value;
    setPlayerName(val);
    if (val.length > 1) {
      try {
        const res = await apiClient.get(
          `/players/search?q=${val}&pos=${posFilter}&league_id=${activeLeagueId}`
        );
        const draftedIds = new Set(history.map((h) => h.player_id));
        const filtered = res.data
          .filter((p) => !draftedIds.has(p.id) && isActiveDraftPlayer(p))
          .sort((a, b) => {
            const rankA = rankingByPlayerId.get(a.id)?.rank ?? 9999;
            const rankB = rankingByPlayerId.get(b.id)?.rank ?? 9999;
            if (rankA !== rankB) return rankA - rankB;
            return (a.name || '').localeCompare(b.name || '');
          });
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
      apiClient.get(`/players/?league_id=${leagueIdInt}`).then((res) => setPlayers(res.data));
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
          const nextActivePositions = getLeagueActivePositions(res.data);
          setActivePositions(
            nextActivePositions.length > 0 ? nextActivePositions : PLAYER_POSITIONS
          );
          if (res.data?.draft_year) {
            setDraftYear(res.data.draft_year);
          }
          if (res.data?.roster_size) {
            setRosterSize(Number(res.data.roster_size) || ROSTER_SIZE);
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
    if (posFilter === 'ALL') return;
    if (!activePositions.includes(posFilter)) {
      setPosFilter('ALL');
    }
  }, [activePositions, posFilter]);

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

  useEffect(() => {
    if (!draftYear) return;
    const rankingOwnerId = Number(effectiveWinnerId || activeOwnerId || 0) || null;
    const rankingLeagueId = Number(activeLeagueId || 0) || null;

    const params = new URLSearchParams();
    params.append('season', String(draftYear));
    params.append('limit', '75');
    if (rankingLeagueId) {
      params.append('league_id', String(rankingLeagueId));
    }
    if (rankingOwnerId) {
      params.append('owner_id', String(rankingOwnerId));
    }

    apiClient
      .get(`/draft/rankings?${params.toString()}`)
      .then((res) => {
        setHistoricalRankings(Array.isArray(res.data) ? res.data : []);
      })
      .catch(() => {
        setHistoricalRankings([]);
      });
  }, [draftYear, effectiveWinnerId, activeOwnerId, activeLeagueId]);

  // --- 1.4 DERIVED CALCULATIONS ---
  const currentNominatorId = useMemo(() => {
    if (owners.length === 0) return null;
    return [...owners].sort((a, b) => a.id - b.id)[
      history.length % owners.length
    ].id;
  }, [owners, history.length]);

  const activeStats = useMemo(() => {
    if (!effectiveWinnerId) return null;
    return getOwnerStats(
      effectiveWinnerId,
      history,
      budgetMap,
      undefined,
      rosterSize
    );
  }, [effectiveWinnerId, history, budgetMap, rosterSize]);

  const ownerStatsById = useMemo(() => {
    const map = {};
    owners.forEach((owner) => {
      map[owner.id] = getOwnerStats(
        owner.id,
        history,
        budgetMap,
        undefined,
        rosterSize
      );
    });
    return map;
  }, [owners, history, budgetMap, rosterSize]);

  const ownersWithBudgets = useMemo(() => {
    return owners.map((owner) => ({
      ...owner,
      remaining_budget: ownerStatsById[owner.id]?.budget ?? 0,
    }));
  }, [owners, ownerStatsById]);

  useEffect(() => {
    if (!owners.length) return;
    const currentStats = ownerStatsById[winnerId];
    const isCurrentAffordable =
      !!currentStats &&
      !currentStats.isFull &&
      bidAmount <= currentStats.maxBid;

    if (isCurrentAffordable) return;

    const nextOwner = owners.find((owner) => {
      const stats = ownerStatsById[owner.id];
      return !!stats && !stats.isFull && bidAmount <= stats.maxBid;
    });

    if (nextOwner) {
      setWinnerId(nextOwner.id);
    }
  }, [owners, winnerId, bidAmount, ownerStatsById]);

  // keep bid input within valid bounds for selected owner where possible
  useEffect(() => {
    if (!activeStats) return;
    if (activeStats.maxBid <= 0) return;
    if (bidAmount > activeStats.maxBid) {
      setBidAmount(activeStats.maxBid);
    }
  }, [activeStats, bidAmount]);

  const canCurrentWinnerAfford =
    !!activeStats && !activeStats.isFull && bidAmount <= activeStats.maxBid;

  const canSubmitDraft = Boolean(
    playerName && effectiveWinnerId && canCurrentWinnerAfford
  );

  const winnerBudget = activeStats?.budget ?? 0;
  const winnerMaxBidAllowed = activeStats?.maxBid ?? 0;
  const winnerOpenSlotsAllowed = activeStats?.emptySpots ?? 0;
  const winnerRosterSlotsConfigured = rosterSize;

  const lastDraftedText = useMemo(() => {
    if (!history.length) {
      return '"Player Name" drafted to "Team Name" for "$XX"';
    }
    const latestPick = [...history].sort(
      (a, b) =>
        new Date(b.timestamp || 0).getTime() -
        new Date(a.timestamp || 0).getTime()
    )[0];
    const draftedOwner = owners.find((owner) => owner.id === latestPick.owner_id);
    const draftedTeam =
      draftedOwner?.team_name || draftedOwner?.username || 'Team Name';
    const draftedPlayer = latestPick.player_name || 'Player Name';
    const draftedAmount = Number(latestPick.amount || 0);
    return `"${draftedPlayer}" drafted to "${draftedTeam}" for "$${draftedAmount}"`;
  }, [history, owners]);

  const undraftedPlayerIds = useMemo(
    () => new Set(history.map((pick) => pick.player_id)),
    [history]
  );

  const bestAvailablePlayers = useMemo(() => {
    return players
      .filter(
        (player) => !undraftedPlayerIds.has(player.id) && isActiveDraftPlayer(player)
      )
      .map((player) => ({
        ...player,
        pos: player.position,
        rank: rankingByPlayerId.get(player.id)?.rank ?? player.rank ?? 9999,
        projectedValue:
          rankingByPlayerId.get(player.id)?.predicted_auction_value ??
          player.projectedValue ??
          player.projected_value ??
          player.auction_value ??
          player.value ??
          0,
      }))
      .sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999))
      .slice(0, 100);
  }, [players, undraftedPlayerIds, rankingByPlayerId]);

  useEffect(() => {
    if (!draftPopupData) return undefined;
    const timer = setTimeout(() => setDraftPopupData(null), 2800);
    return () => clearTimeout(timer);
  }, [draftPopupData]);

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
    <PageTemplate
      title="Draft Board"
      subtitle={`${leagueName ? `${leagueName} - ` : ''}Live auction control room.`}
      className="overflow-hidden"
    >

      {/* banner rendered below via SessionHeader */}
      <SessionHeader
        sessionId={sessionId}
        rosterSize={rosterSize}
        leagueName={leagueName}
        username={username}
        isCommissioner={isCommissioner}
        isPaused={isPaused}
        onPause={handlePause}
      />

      {/* auction controls top bar */}
      <div className="w-full">
        <div className="flex flex-wrap items-end justify-start p-1 bg-slate-900/40">
          {/* auction controls panel handles its own internal alignment */}
          <AuctionBlock
            playerName={playerName}
            handleSearchChange={handleSearchChange}
            suggestions={suggestions}
            showSuggestions={showSuggestions}
            selectSuggestion={selectSuggestion}
            positions={activePositions}
            posFilter={posFilter}
            setPosFilter={setPosFilter}
            winnerId={winnerId}
            setWinnerId={setWinnerId}
            owners={owners}
            activeStats={activeStats}
            ownerStatsById={ownerStatsById}
            bidAmount={bidAmount}
            setBidAmount={setBidAmount}
            handleDraft={handleDraft}
            canDraft={canSubmitDraft}
            timeLeft={timeLeft}
            isTimerRunning={isTimerRunning}
            reset={reset}
            start={start}
            nominatorId={currentNominatorId}
            isCommissioner={isCommissioner}
            showBestSidebar={showBestSidebar}
            toggleSidebar={(v) => setShowBestSidebar(v)}
            lastDraftedText={lastDraftedText}
            rosterSize={rosterSize}
            winnerBudget={winnerBudget}
            winnerMaxBidAllowed={winnerMaxBidAllowed}
            winnerOpenSlotsAllowed={winnerOpenSlotsAllowed}
            winnerRosterSlotsConfigured={winnerRosterSlotsConfigured}
          />
        </div>
      </div>

      {/* ticker area */}
      <DraftHistoryFeed history={history} owners={owners} />

      <div className="relative">
        <main className="flex-1 grid grid-cols-12 h-[70vh] md:h-screen gap-0 overflow-hidden z-0">
          <section className="overflow-x-auto border-r border-slate-800 custom-scrollbar col-span-12">
            <DraftBoardGrid
              teams={ownersWithBudgets}
              history={history}
              rosterLimit={rosterSize}
              highlightOwnerId={highlightOwnerId}
              onPlayerClick={openPlayerPerformance}
            />
          </section>
        </main>

        {showBestSidebar && (
          <aside className="absolute right-2 top-2 bottom-2 w-[300px] max-w-[80vw] bg-slate-900/90 border border-slate-700 rounded-lg overflow-hidden z-20 shadow-2xl">
            <BestAvailableList
              open={showBestSidebar}
              onToggle={() => setShowBestSidebar(false)}
              players={bestAvailablePlayers}
            />
          </aside>
        )}
      </div>

      {draftPopupData && (
        <div className={`fixed inset-0 ${layerModal} flex items-center justify-center pointer-events-none`}>
          <div className="bg-sky-500 text-white border-2 border-sky-300 px-10 py-8 text-center shadow-2xl min-w-[420px] max-w-[92vw]">
            <div className="text-6xl leading-tight font-medium">{draftPopupData.playerName}</div>
            <div className="text-6xl leading-tight font-light mt-2">Drafted to</div>
            <div className="text-7xl leading-tight font-medium mt-2">{draftPopupData.teamName}</div>
            <div className="text-6xl leading-tight font-light mt-3">
              For <span className="text-8xl">${draftPopupData.amount}</span>
            </div>
          </div>
        </div>
      )}

      <footer className="bg-slate-900 px-4 md:px-6 py-1 flex justify-between text-[10px] text-slate-500 border-t border-slate-800">
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
              <div className="py-10 text-center">
                <LoadingState message="Loading season details..." className="justify-center" />
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
                  teamLogoUrl={playerPerformance.team_logo_url || ''}
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
                      <div className="p-6 text-center">
                        <EmptyState
                          message="No weekly performance data yet for this season."
                          className="justify-center"
                        />
                      </div>
                    ) : (
                      <StandardTable>
                        <StandardTableHead
                          headers={[
                            { key: 'week', label: 'Week', className: 'px-4 py-2' },
                            {
                              key: 'fantasyPoints',
                              label: 'Fantasy Pts',
                              className: 'px-4 py-2 text-right',
                            },
                          ]}
                        />
                        <tbody>
                          {playerPerformance.weekly.map((row) => (
                            <StandardTableRow key={row.week} className="hover:bg-transparent dark:hover:bg-transparent">
                              <td className={tableCell}>Week {row.week}</td>
                              <td className={`${tableCellNumeric} font-mono text-blue-400`}>
                                {Number(row.fantasy_points || 0).toFixed(2)}
                              </td>
                            </StandardTableRow>
                          ))}
                        </tbody>
                      </StandardTable>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="py-10 text-center">
                <EmptyState
                  message="No season details available."
                  className="justify-center"
                />
              </div>
            )}
          </div>
        </div>
      )}
    </PageTemplate>
  );
}
