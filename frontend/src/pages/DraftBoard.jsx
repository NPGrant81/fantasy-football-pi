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
import PlayerInsightCard from '@components/draft/insights/PlayerInsightCard';
import OwnerStrategyPanel from '@components/draft/insights/OwnerStrategyPanel';
import DraftDynamicsPanel from '@components/draft/insights/DraftDynamicsPanel';
import {
  POSITION_CAPS,
  STRATEGY_MAX_SPEND_SHARE,
  normalizePos,
} from '@components/draft/insights/insightVocabulary';
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
  const [showPlayerPerformance, setShowPlayerPerformance] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [playerPerformance, setPlayerPerformance] = useState(null);
  const [playerPerformanceLoading, setPlayerPerformanceLoading] =
    useState(false);
  const [draftPopupData, setDraftPopupData] = useState(null);
  const [historicalRankings, setHistoricalRankings] = useState([]);
  const [rankingsLoading, setRankingsLoading] = useState(false);
  const [simulationPerspectiveOwnerId, setSimulationPerspectiveOwnerId] =
    useState('');
  const [simulationIterations, setSimulationIterations] = useState(500);
  const [simulationAggressiveness, setSimulationAggressiveness] =
    useState(1.0);
  const [simulationRiskTolerance, setSimulationRiskTolerance] = useState(0.5);
  const [simulationReliability, setSimulationReliability] = useState(1.0);
  const [simulationQbWeight, setSimulationQbWeight] = useState(1.0);
  const [simulationRbWeight, setSimulationRbWeight] = useState(1.0);
  const [simulationWrWeight, setSimulationWrWeight] = useState(1.0);
  const [simulationTeWeight, setSimulationTeWeight] = useState(1.0);
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [simulationError, setSimulationError] = useState('');
  const [simulationResult, setSimulationResult] = useState(null);
  const [advisorLoading, setAdvisorLoading] = useState(false);
  const [advisorError, setAdvisorError] = useState('');
  const [advisorMessage, setAdvisorMessage] = useState(null);
  const [lastNominationKey, setLastNominationKey] = useState('');
  const [lastBidEventKey, setLastBidEventKey] = useState('');
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState('');
  const [modelInsights, setModelInsights] = useState(null);

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

  useEffect(() => {
    if (!owners.length) return;
    if (simulationPerspectiveOwnerId) return;
    const fallback =
      Number(activeOwnerId || effectiveWinnerId || owners[0]?.id || 0) ||
      owners[0].id;
    setSimulationPerspectiveOwnerId(String(fallback));
  }, [owners, simulationPerspectiveOwnerId, activeOwnerId, effectiveWinnerId]);

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
          `/players/search?q=${val}&pos=${posFilter}`
        );
        const draftedIds = new Set(history.map((h) => h.player_id));
        const filtered = res.data
          .filter((p) => !draftedIds.has(p.id))
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

    setRankingsLoading(true);
    apiClient
      .get(`/draft/rankings?${params.toString()}`)
      .then((res) => {
        setHistoricalRankings(Array.isArray(res.data) ? res.data : []);
      })
      .catch(() => {
        setHistoricalRankings([]);
      })
      .finally(() => {
        setRankingsLoading(false);
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
      .filter((player) => !undraftedPlayerIds.has(player.id))
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

  const selectedPlayerForAdvisor = useMemo(() => {
    if (!playerName) return null;
    const found = players.find(
      (player) =>
        String(player.name || '').toLowerCase() ===
        String(playerName || '').toLowerCase()
    );
    if (!found) return null;
    if (undraftedPlayerIds.has(found.id)) return null;
    return found;
  }, [playerName, players, undraftedPlayerIds]);

  const insightOwnerId = useMemo(() => {
    if (!isCommissioner) {
      return Number(highlightOwnerId || activeOwnerId || effectiveWinnerId || 0) || 0;
    }
    return Number(effectiveWinnerId || highlightOwnerId || activeOwnerId || 0) || 0;
  }, [isCommissioner, highlightOwnerId, activeOwnerId, effectiveWinnerId]);

  const ownerPositionSpendAndCounts = useMemo(() => {
    const byOwner = {};
    owners.forEach((owner) => {
      byOwner[owner.id] = {
        spend: { QB: 0, RB: 0, WR: 0, TE: 0, DEF: 0, K: 0 },
        count: { QB: 0, RB: 0, WR: 0, TE: 0, DEF: 0, K: 0 },
      };
    });

    history.forEach((pick) => {
      const ownerId = Number(pick.owner_id || 0);
      if (!ownerId || !byOwner[ownerId]) return;
      const position = normalizePos(
        pick.position ||
          rankingByPlayerId.get(Number(pick.player_id || 0))?.position ||
          players.find((player) => Number(player.id) === Number(pick.player_id || 0))
            ?.position
      );
      if (!byOwner[ownerId].spend[position]) return;
      byOwner[ownerId].spend[position] += Number(pick.amount || 0);
      byOwner[ownerId].count[position] += 1;
    });

    return byOwner;
  }, [owners, history, rankingByPlayerId, players]);

  const draftDynamics = useMemo(() => {
    const ownersWithStats = owners
      .map((owner) => ({ owner, stats: ownerStatsById[owner.id] }))
      .filter((row) => !!row.stats);

    const budgetDistribution = ownersWithStats
      .map((row) => ({
        owner_id: row.owner.id,
        owner_name: row.owner.team_name || row.owner.username || `Owner ${row.owner.id}`,
        budget: Number(row.stats.budget || 0),
      }))
      .sort((a, b) => b.budget - a.budget);

    const leagueAvgBudget =
      budgetDistribution.length > 0
        ? budgetDistribution.reduce((sum, item) => sum + item.budget, 0) /
          budgetDistribution.length
        : 0;

    const byPositionDemand = Object.keys(POSITION_CAPS).map((position) => {
      const remainingSlots = ownersWithStats.reduce((sum, row) => {
        const currentCount =
          ownerPositionSpendAndCounts[row.owner.id]?.count?.[position] || 0;
        return sum + Math.max(POSITION_CAPS[position] - currentCount, 0);
      }, 0);

      const availableCount = bestAvailablePlayers.filter(
        (player) => normalizePos(player.pos || player.position) === position
      ).length;

      const scarcity =
        availableCount <= 0
          ? 100
          : Math.min(100, Math.round((remainingSlots / availableCount) * 100));

      const replacementValuePool = bestAvailablePlayers
        .filter((player) => normalizePos(player.pos || player.position) === position)
        .slice(8, 18);
      const replacementLevelValue =
        replacementValuePool.length > 0
          ? replacementValuePool.reduce(
              (sum, player) =>
                sum + Number(player.projectedValue || 0),
              0
            ) / replacementValuePool.length
          : 0;

      return {
        position,
        remainingSlots,
        availableCount,
        scarcity,
        replacementLevelValue,
      };
    });

    const recentPicks = [...history]
      .sort(
        (a, b) =>
          new Date(a.timestamp || 0).getTime() -
          new Date(b.timestamp || 0).getTime()
      )
      .slice(-12);
    const inflationIndex =
      recentPicks.length > 0
        ? recentPicks.reduce((sum, pick) => {
            const predicted = Number(
              rankingByPlayerId.get(Number(pick.player_id || 0))
                ?.predicted_auction_value || 1
            );
            return sum + Number(pick.amount || 0) / Math.max(predicted, 1);
          }, 0) / recentPicks.length
        : 1;

    return {
      budgetDistribution,
      leagueAvgBudget,
      byPositionDemand,
      inflationIndex,
    };
  }, [
    owners,
    ownerStatsById,
    ownerPositionSpendAndCounts,
    bestAvailablePlayers,
    history,
    rankingByPlayerId,
  ]);

  const selectedInsightRecommendation = useMemo(() => {
    if (!modelInsights?.recommendations?.length) return null;
    const selectedPlayerId = Number(selectedPlayerForAdvisor?.id || 0);
    if (selectedPlayerId) {
      const exact = modelInsights.recommendations.find(
        (recommendation) => Number(recommendation.player_id) === selectedPlayerId
      );
      if (exact) return exact;
    }
    return modelInsights.recommendations[0] || null;
  }, [modelInsights, selectedPlayerForAdvisor]);

  useEffect(() => {
    if (!activeLeagueId || !draftYear || !insightOwnerId) return;

    const timeoutId = setTimeout(async () => {
      const draftedPlayerIds = history
        .map((pick) => Number(pick.player_id || 0))
        .filter(Boolean);

      const remainingBudgetByOwner = {};
      const remainingSlotsByOwner = {};
      owners.forEach((owner) => {
        const stats = ownerStatsById[owner.id];
        if (!stats) return;
        remainingBudgetByOwner[owner.id] = Number(stats.budget ?? 0);
        remainingSlotsByOwner[owner.id] = Number(stats.emptySpots ?? 0);
      });

      const selectedPlayerId = Number(selectedPlayerForAdvisor?.id || 0);
      const candidatePool = selectedPlayerId
        ? [
            selectedPlayerId,
            ...bestAvailablePlayers
              .filter(
                (player) =>
                  normalizePos(player.pos || player.position) ===
                  normalizePos(selectedPlayerForAdvisor?.position)
              )
              .slice(0, 8)
              .map((player) => Number(player.id)),
          ]
        : bestAvailablePlayers.slice(0, 12).map((player) => Number(player.id));

      const uniquePlayerIds = [...new Set(candidatePool.filter(Boolean))];

      setInsightsLoading(true);
      setInsightsError('');
      try {
        const payload = {
          owner_id: Number(insightOwnerId),
          season: Number(draftYear),
          league_id: Number(activeLeagueId),
          player_ids: uniquePlayerIds,
          limit: 12,
          model_version: 'current',
          draft_state: {
            drafted_player_ids: draftedPlayerIds,
            remaining_budget_by_owner: remainingBudgetByOwner,
            remaining_slots_by_owner: remainingSlotsByOwner,
          },
        };

        const response = await apiClient.post('/draft/model/predict', payload);
        setModelInsights(response?.data || null);
      } catch (error) {
        setInsightsError(
          error?.response?.data?.detail ||
            'Unable to refresh model insights right now.'
        );
      } finally {
        setInsightsLoading(false);
      }
    }, 350);

    return () => clearTimeout(timeoutId);
  }, [
    activeLeagueId,
    draftYear,
    insightOwnerId,
    history,
    owners,
    ownerStatsById,
    selectedPlayerForAdvisor,
    bestAvailablePlayers,
  ]);

  const ownerStrategyInsights = useMemo(() => {
    const ownerStats = ownerStatsById[insightOwnerId];
    if (!ownerStats) return null;

    const ownerSpendByPos = ownerPositionSpendAndCounts[insightOwnerId]?.spend || {
      QB: 0,
      RB: 0,
      WR: 0,
      TE: 0,
      DEF: 0,
      K: 0,
    };
    const ownerCountByPos = ownerPositionSpendAndCounts[insightOwnerId]?.count || {
      QB: 0,
      RB: 0,
      WR: 0,
      TE: 0,
      DEF: 0,
      K: 0,
    };

    const leagueAvgByPos = {};
    Object.keys(POSITION_CAPS).forEach((position) => {
      const values = owners
        .map((owner) => ownerPositionSpendAndCounts[owner.id]?.count?.[position] ?? 0)
        .filter((value) => Number.isFinite(value));
      leagueAvgByPos[position] =
        values.length > 0
          ? values.reduce((sum, value) => sum + value, 0) / values.length
          : 0;
    });

    const positionalBalance = Object.keys(POSITION_CAPS).map((position) => {
      const delta = Number(ownerCountByPos[position] || 0) - Number(leagueAvgByPos[position] || 0);
      return {
        position,
        owner: Number(ownerCountByPos[position] || 0),
        leagueAvg: Number(leagueAvgByPos[position] || 0),
        delta,
      };
    });

    const mostBehindPosition = [...positionalBalance].sort(
      (a, b) => a.delta - b.delta
    )[0];

    const ownerSpendPerFilledSlot =
      ownerStats.filledSpots > 0
        ? Number(ownerStats.spent || 0) / Number(ownerStats.filledSpots)
        : 0;
    const leagueSpendPerFilledSlot =
      owners.length > 0
        ? owners.reduce((sum, owner) => {
            const stats = ownerStatsById[owner.id];
            if (!stats || !stats.filledSpots) return sum;
            return sum + Number(stats.spent || 0) / Number(stats.filledSpots);
          }, 0) / owners.length
        : 0;

    const aggressivenessIndex =
      leagueSpendPerFilledSlot > 0
        ? ownerSpendPerFilledSlot / leagueSpendPerFilledSlot
        : 1;

    const selectedPos = normalizePos(
      selectedInsightRecommendation?.position || selectedPlayerForAdvisor?.position
    );
    const selectedPosSpend = Number(ownerSpendByPos[selectedPos] || 0);
    const posMaxSpend = Number(ownerStats.initialBudget || 0) *
      Number(STRATEGY_MAX_SPEND_SHARE[selectedPos] || 0.2);
    const exceedsPosCap =
      selectedPos && selectedInsightRecommendation?.recommended_bid != null
        ? selectedPosSpend + Number(selectedInsightRecommendation.recommended_bid) > posMaxSpend
        : false;

    const bidAlignment = (() => {
      if (!selectedInsightRecommendation) return 1;
      const recBid = Number(selectedInsightRecommendation.recommended_bid || 0);
      if (recBid <= 0) return 1;
      const ratio = Number(bidAmount || 0) / recBid;
      if (ratio <= 1.05) return 1;
      if (ratio <= 1.2) return 0.7;
      return 0.35;
    })();

    const balancePenalty =
      mostBehindPosition && mostBehindPosition.delta < -1
        ? Math.min(0.4, Math.abs(mostBehindPosition.delta) * 0.12)
        : 0;
    const budgetPenalty = ownerStats.maxBid < Number(bidAmount || 0) ? 0.45 : 0;

    const strategyAlignmentScore = Math.max(
      0,
      Math.min(100, Math.round((bidAlignment - balancePenalty - budgetPenalty) * 100))
    );

    return {
      ownerStats,
      leagueAvgBudget: Number(draftDynamics.leagueAvgBudget || 0),
      positionalBalance,
      mostBehindPosition,
      aggressivenessIndex,
      strategyAlignmentScore,
      selectedPos,
      selectedPosSpend,
      posMaxSpend,
      exceedsPosCap,
    };
  }, [
    ownerStatsById,
    insightOwnerId,
    ownerPositionSpendAndCounts,
    owners,
    selectedInsightRecommendation,
    selectedPlayerForAdvisor,
    bidAmount,
    draftDynamics.leagueAvgBudget,
  ]);

  const availableHistoricalRankings = useMemo(() => {
    return historicalRankings
      .filter((entry) => !undraftedPlayerIds.has(entry.player_id))
      .slice(0, 12);
  }, [historicalRankings, undraftedPlayerIds]);

  const handleRunSimulation = useCallback(async () => {
    const focalOwnerId = Number(simulationPerspectiveOwnerId || 0);
    if (!focalOwnerId) {
      setSimulationError('Choose an owner perspective first.');
      return;
    }

    setSimulationLoading(true);
    setSimulationError('');

    const toWeight = (value) => {
      const numeric = Number(value);
      if (!Number.isFinite(numeric) || numeric <= 0) return 1.0;
      return numeric;
    };

    try {
      const payload = {
        perspective_owner_id: focalOwnerId,
        iterations: Math.max(50, Math.min(10000, Number(simulationIterations) || 500)),
        seed: Number(draftYear || new Date().getFullYear()),
        teams_count: Math.max(2, owners.length || 12),
        roster_size: Number(rosterSize || ROSTER_SIZE),
        strategy: {
          aggressiveness_multiplier: toWeight(simulationAggressiveness),
          risk_tolerance: Math.max(0, Math.min(1, Number(simulationRiskTolerance) || 0.5)),
          player_reliability_weight: toWeight(simulationReliability),
          position_weights: {
            QB: toWeight(simulationQbWeight),
            RB: toWeight(simulationRbWeight),
            WR: toWeight(simulationWrWeight),
            TE: toWeight(simulationTeWeight),
          },
        },
      };

      const res = await apiClient.post('/draft/simulation', payload);
      setSimulationResult(res.data || null);
    } catch (error) {
      setSimulationResult(null);
      setSimulationError(
        error?.response?.data?.detail || 'Simulation failed. Please try again.'
      );
    } finally {
      setSimulationLoading(false);
    }
  }, [
    simulationPerspectiveOwnerId,
    simulationIterations,
    simulationAggressiveness,
    simulationRiskTolerance,
    simulationReliability,
    simulationQbWeight,
    simulationRbWeight,
    simulationWrWeight,
    simulationTeWeight,
    draftYear,
    owners.length,
    rosterSize,
  ]);

  const buildDraftDayState = useCallback(() => {
    const draftedPlayerIds = history.map((pick) => Number(pick.player_id)).filter(Boolean);

    const remainingBudgetByOwner = {};
    const remainingSlotsByOwner = {};
    const positionCountsByOwner = {};

    owners.forEach((owner) => {
      const stats = ownerStatsById[owner.id];
      if (stats) {
        remainingBudgetByOwner[owner.id] = Number(stats.budget ?? 0);
        remainingSlotsByOwner[owner.id] = Number(stats.emptySpots ?? 0);
      }
      positionCountsByOwner[owner.id] = {
        QB: 0,
        RB: 0,
        WR: 0,
        TE: 0,
        DEF: 0,
        K: 0,
      };
    });

    history.forEach((pick) => {
      const ownerId = Number(pick.owner_id);
      if (!ownerId || !positionCountsByOwner[ownerId]) return;
      const fallbackPosition =
        rankingByPlayerId.get(Number(pick.player_id))?.position ||
        players.find((player) => Number(player.id) === Number(pick.player_id))?.position ||
        '';
      const normalizedPosition = String(pick.position || fallbackPosition || '')
        .toUpperCase()
        .replace('D/ST', 'DEF')
        .replace('DST', 'DEF');
      if (positionCountsByOwner[ownerId][normalizedPosition] != null) {
        positionCountsByOwner[ownerId][normalizedPosition] += 1;
      }
    });

    const recentNominations = history
      .slice(-8)
      .map((pick) => {
        const fallbackPosition =
          rankingByPlayerId.get(Number(pick.player_id))?.position ||
          players.find((player) => Number(player.id) === Number(pick.player_id))?.position ||
          '';
        return String(pick.position || fallbackPosition || '')
          .toUpperCase()
          .replace('D/ST', 'DEF')
          .replace('DST', 'DEF');
      })
      .filter(Boolean);

    return {
      drafted_player_ids: draftedPlayerIds,
      remaining_budget_by_owner: remainingBudgetByOwner,
      remaining_slots_by_owner: remainingSlotsByOwner,
      position_counts_by_owner: positionCountsByOwner,
      recent_nominations: recentNominations,
    };
  }, [history, owners, ownerStatsById, rankingByPlayerId, players]);

  const postDraftDayEvent = useCallback(
    async ({
      eventType,
      playerId,
      currentBid,
      comparedPlayerId,
      question,
      isQuery = false,
    }) => {
      const ownerId = Number(effectiveWinnerId || 0);
      const leagueId = Number(activeLeagueId || 0);
      const season = Number(draftYear || new Date().getFullYear());
      if (!ownerId || !leagueId || !season) return;

      setAdvisorLoading(true);
      setAdvisorError('');

      const payload = {
        owner_id: ownerId,
        season,
        league_id: leagueId,
        event_type: eventType,
        player_id: playerId ? Number(playerId) : null,
        current_bid: currentBid != null ? Number(currentBid) : null,
        compared_player_id: comparedPlayerId ? Number(comparedPlayerId) : null,
        question: question || null,
        draft_state: buildDraftDayState(),
      };

      try {
        const endpoint = isQuery ? '/advisor/draft-day/query' : '/advisor/draft-day/event';
        const response = await apiClient.post(endpoint, payload);
        setAdvisorMessage(response?.data || null);
      } catch (error) {
        setAdvisorError(
          error?.response?.data?.detail ||
            'Draft Day advisor request failed. Please retry.'
        );
      } finally {
        setAdvisorLoading(false);
      }
    },
    [effectiveWinnerId, activeLeagueId, draftYear, buildDraftDayState]
  );

  const handleAdvisorQuickAction = useCallback(
    async (action) => {
      const playerId = Number(selectedPlayerForAdvisor?.id || 0) || null;
      if (action === 'Simulate') {
        await handleRunSimulation();
        return;
      }

      if (action === 'Compare') {
        const alternative = (advisorMessage?.suggested_alternatives || [])[0];
        const comparedPlayerId = Number(alternative?.player_id || 0) || null;
        if (!playerId || !comparedPlayerId) return;
        await postDraftDayEvent({
          eventType: 'user_query',
          playerId,
          comparedPlayerId,
          question: 'Compare these two players',
          isQuery: true,
        });
        return;
      }

      if (!playerId) return;
      await postDraftDayEvent({
        eventType: 'user_query',
        playerId,
        currentBid: Number(bidAmount || 0),
        question: 'Explain this recommendation.',
        isQuery: true,
      });
    },
    [selectedPlayerForAdvisor, advisorMessage, postDraftDayEvent, bidAmount, handleRunSimulation]
  );

  useEffect(() => {
    if (!selectedPlayerForAdvisor || !effectiveWinnerId || !activeLeagueId) return;
    const nominationKey = [
      Number(selectedPlayerForAdvisor.id || 0),
      Number(effectiveWinnerId || 0),
      Number(activeLeagueId || 0),
      Number(draftYear || 0),
      history.length,
    ].join(':');
    if (nominationKey === lastNominationKey) return;

    const timeoutId = setTimeout(() => {
      postDraftDayEvent({
        eventType: 'nomination',
        playerId: Number(selectedPlayerForAdvisor.id),
        currentBid: Number(bidAmount || 0),
      });
      setLastNominationKey(nominationKey);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [
    selectedPlayerForAdvisor,
    effectiveWinnerId,
    activeLeagueId,
    draftYear,
    history.length,
    bidAmount,
    lastNominationKey,
    postDraftDayEvent,
  ]);

  useEffect(() => {
    if (!selectedPlayerForAdvisor || !effectiveWinnerId) return;
    const bidEventKey = [
      Number(selectedPlayerForAdvisor.id || 0),
      Number(effectiveWinnerId || 0),
      Number(bidAmount || 0),
      history.length,
    ].join(':');
    if (bidEventKey === lastBidEventKey) return;

    const timeoutId = setTimeout(() => {
      postDraftDayEvent({
        eventType: 'bid_update',
        playerId: Number(selectedPlayerForAdvisor.id),
        currentBid: Number(bidAmount || 0),
      });
      setLastBidEventKey(bidEventKey);
    }, 250);

    return () => clearTimeout(timeoutId);
  }, [
    selectedPlayerForAdvisor,
    effectiveWinnerId,
    bidAmount,
    history.length,
    lastBidEventKey,
    postDraftDayEvent,
  ]);

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

      <section className="mt-3 rounded-lg border border-emerald-900/70 bg-slate-900/60 p-3 col-span-12">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-emerald-300">
            Analyzer Insights
          </h2>
          <span className="text-[11px] text-slate-500">
            Vocabulary: ValueScore, Scarcity, Risk, BargainFlag, StrategyAlignment
          </span>
        </div>

        {insightsError ? (
          <div className="mb-2 text-xs text-rose-300">{insightsError}</div>
        ) : null}

        {insightsLoading ? (
          <div className="mb-2 text-xs text-slate-400">Refreshing model insights...</div>
        ) : null}

        <div className="grid gap-3 xl:grid-cols-3">
          <PlayerInsightCard
            recommendation={selectedInsightRecommendation}
            bidAmount={bidAmount}
          />

          <OwnerStrategyPanel
            insightOwnerId={insightOwnerId}
            ownerStrategyInsights={ownerStrategyInsights}
            recommendation={selectedInsightRecommendation}
          />

          <DraftDynamicsPanel draftDynamics={draftDynamics} />
        </div>
      </section>

      <section className="mt-3 rounded-lg border border-slate-800 bg-slate-900/60 p-3">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-300">
            Historical Rankings
          </h2>
          <span className="text-[11px] text-slate-500">Season {draftYear}</span>
        </div>
        {rankingsLoading ? (
          <div className="py-2 text-xs text-slate-400">Loading rankings...</div>
        ) : availableHistoricalRankings.length === 0 ? (
          <div className="py-2 text-xs text-slate-500">
            No historical rankings available.
          </div>
        ) : (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {availableHistoricalRankings.map((entry) => (
              <div
                key={entry.player_id}
                className="rounded-md border border-slate-800 bg-slate-950/60 p-2"
              >
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>#{entry.rank}</span>
                  <span>{entry.consensus_tier || 'C'} tier</span>
                </div>
                <div className="mt-1 truncate text-sm font-semibold text-slate-100">
                  {entry.player_name}
                </div>
                <div className="mt-1 flex items-center justify-between text-xs text-slate-400">
                  <span>{entry.position || 'UNK'}</span>
                  <span className="text-emerald-400">
                    ${Number(entry.predicted_auction_value || 0).toFixed(0)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="mt-3 rounded-lg border border-indigo-900/70 bg-slate-900/60 p-3">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-indigo-300">
            Draft Day Advisor
          </h2>
          <span className="text-[11px] text-slate-500">
            Triggered by nomination and bid updates
          </span>
        </div>

        {advisorError ? (
          <div className="mb-2 text-xs text-rose-300">{advisorError}</div>
        ) : null}

        {advisorLoading ? (
          <div className="text-xs text-slate-400">Updating advisor...</div>
        ) : null}

        {!advisorMessage ? (
          <div className="text-xs text-slate-500">
            Select a draftable player and adjust bid to receive live advisor guidance.
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">
                {advisorMessage.message_type || 'recommendation'}
              </div>
              <div className="mt-1 text-sm font-semibold text-indigo-200">
                {advisorMessage.headline || 'Draft Day advisor'}
              </div>
              <div className="mt-2 text-xs leading-5 text-slate-300">
                {advisorMessage.body || ''}
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-300">
                <div>
                  <div className="text-slate-500">Recommended Bid</div>
                  <div className="font-semibold text-indigo-300">
                    {advisorMessage.recommended_bid != null
                      ? `$${Number(advisorMessage.recommended_bid).toFixed(2)}`
                      : '-'}
                  </div>
                </div>
                <div>
                  <div className="text-slate-500">War Likelihood</div>
                  <div className="font-semibold text-indigo-300">
                    {advisorMessage.bidding_war_likelihood != null
                      ? `${Number(advisorMessage.bidding_war_likelihood).toFixed(1)}%`
                      : '-'}
                  </div>
                </div>
                <div>
                  <div className="text-slate-500">Tier</div>
                  <div className="font-semibold">{advisorMessage.value_tier || '-'}</div>
                </div>
                <div>
                  <div className="text-slate-500">Risk Score</div>
                  <div className="font-semibold">
                    {advisorMessage.risk_score != null
                      ? Number(advisorMessage.risk_score).toFixed(1)
                      : '-'}
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">
                Alerts & Actions
              </div>
              {Array.isArray(advisorMessage.alerts) && advisorMessage.alerts.length > 0 ? (
                <div className="mt-2 space-y-1 text-xs text-amber-300">
                  {advisorMessage.alerts.map((alert, index) => (
                    <div key={`${alert}-${index}`} className="border-t border-slate-800 py-1">
                      {alert}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-2 text-xs text-slate-500">No active alerts.</div>
              )}

              <div className="mt-3 flex flex-wrap gap-2">
                {(advisorMessage.quick_actions || ['Compare', 'Simulate', 'Explain'])
                  .slice(0, 3)
                  .map((action) => (
                    <button
                      key={action}
                      type="button"
                      onClick={() => handleAdvisorQuickAction(action)}
                      className="rounded border border-indigo-800 bg-indigo-950 px-2 py-1 text-xs font-semibold text-indigo-200 transition hover:bg-indigo-900"
                    >
                      {action}
                    </button>
                  ))}
              </div>

              {Array.isArray(advisorMessage.suggested_alternatives) &&
              advisorMessage.suggested_alternatives.length > 0 ? (
                <div className="mt-3 text-xs text-slate-300">
                  <div className="mb-1 text-slate-500">Suggested alternatives</div>
                  {advisorMessage.suggested_alternatives.slice(0, 3).map((item) => (
                    <div
                      key={item.player_id}
                      className="flex items-center justify-between border-t border-slate-800 py-1"
                    >
                      <span className="truncate pr-2">{item.player_name}</span>
                      <span className="text-indigo-300">
                        ${Number(item.predicted_value || 0).toFixed(0)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        )}
      </section>

      <section className="mt-3 rounded-lg border border-cyan-900/70 bg-slate-900/60 p-3">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-cyan-300">
            Perspective Simulation
          </h2>
          <span className="text-[11px] text-slate-500">Request-only knobs</span>
        </div>

        <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
          <label className="text-[11px] text-slate-400">
            Owner Perspective
            <select
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              value={simulationPerspectiveOwnerId}
              onChange={(e) => setSimulationPerspectiveOwnerId(e.target.value)}
            >
              {owners.map((owner) => (
                <option key={owner.id} value={owner.id}>
                  {owner.team_name || owner.username || `Owner ${owner.id}`}
                </option>
              ))}
            </select>
          </label>

          <label className="text-[11px] text-slate-400">
            Iterations
            <input
              type="number"
              min="50"
              max="10000"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              value={simulationIterations}
              onChange={(e) => setSimulationIterations(e.target.value)}
            />
          </label>

          <label className="text-[11px] text-slate-400">
            Aggressiveness
            <input
              type="number"
              step="0.05"
              min="0.5"
              max="2.5"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              value={simulationAggressiveness}
              onChange={(e) => setSimulationAggressiveness(e.target.value)}
            />
          </label>

          <label className="text-[11px] text-slate-400">
            Risk Tolerance
            <input
              type="number"
              step="0.05"
              min="0"
              max="1"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              value={simulationRiskTolerance}
              onChange={(e) => setSimulationRiskTolerance(e.target.value)}
            />
          </label>

          <label className="text-[11px] text-slate-400">
            Reliability Weight
            <input
              type="number"
              step="0.05"
              min="0.5"
              max="2"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              value={simulationReliability}
              onChange={(e) => setSimulationReliability(e.target.value)}
            />
          </label>

          <div className="flex items-end">
            <button
              type="button"
              onClick={handleRunSimulation}
              disabled={simulationLoading}
              className="w-full rounded border border-cyan-700 bg-cyan-950 px-2 py-1 text-xs font-semibold text-cyan-200 transition hover:bg-cyan-900 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {simulationLoading ? 'Running…' : 'Run Simulation'}
            </button>
          </div>
        </div>

        <div className="mt-2 grid gap-2 md:grid-cols-4">
          <label className="text-[11px] text-slate-400">
            QB Weight
            <input
              type="number"
              step="0.05"
              min="0.5"
              max="2"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              value={simulationQbWeight}
              onChange={(e) => setSimulationQbWeight(e.target.value)}
            />
          </label>
          <label className="text-[11px] text-slate-400">
            RB Weight
            <input
              type="number"
              step="0.05"
              min="0.5"
              max="2"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              value={simulationRbWeight}
              onChange={(e) => setSimulationRbWeight(e.target.value)}
            />
          </label>
          <label className="text-[11px] text-slate-400">
            WR Weight
            <input
              type="number"
              step="0.05"
              min="0.5"
              max="2"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              value={simulationWrWeight}
              onChange={(e) => setSimulationWrWeight(e.target.value)}
            />
          </label>
          <label className="text-[11px] text-slate-400">
            TE Weight
            <input
              type="number"
              step="0.05"
              min="0.5"
              max="2"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              value={simulationTeWeight}
              onChange={(e) => setSimulationTeWeight(e.target.value)}
            />
          </label>
        </div>

        {simulationError ? (
          <div className="mt-2 text-xs text-rose-300">{simulationError}</div>
        ) : null}

        {simulationResult ? (
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <div className="rounded-md border border-slate-800 bg-slate-950/60 p-2">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">
                Focal Summary
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-300">
                <div>
                  <div className="text-slate-500">Expected Points</div>
                  <div className="font-semibold text-cyan-300">
                    {Number(
                      simulationResult?.focal_owner_summary
                        ?.expected_total_points || 0
                    ).toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="text-slate-500">Expected Spend</div>
                  <div className="font-semibold text-cyan-300">
                    ${Number(
                      simulationResult?.focal_owner_summary
                        ?.expected_total_spend || 0
                    ).toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="text-slate-500">P50 Points</div>
                  <div className="font-semibold">
                    {Number(
                      simulationResult?.focal_points_distribution
                        ?.points_p50 || 0
                    ).toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="text-slate-500">Vs League Avg</div>
                  <div className="font-semibold">
                    {Number(
                      simulationResult?.league_context?.delta_vs_league_avg || 0
                    ).toFixed(1)}
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-md border border-slate-800 bg-slate-950/60 p-2">
              <div className="text-[11px] uppercase tracking-wide text-slate-400">
                Key Target Probabilities
              </div>
              {Array.isArray(simulationResult?.key_target_probabilities) &&
              simulationResult.key_target_probabilities.length > 0 ? (
                <div className="mt-2 max-h-36 overflow-y-auto text-xs">
                  {simulationResult.key_target_probabilities
                    .slice(0, 8)
                    .map((row) => (
                      <div
                        key={row.player_id}
                        className="flex items-center justify-between border-t border-slate-800 py-1 text-slate-300"
                      >
                        <span className="truncate pr-2">{row.player_name}</span>
                        <span className="font-mono text-cyan-300">
                          {(Number(row.probability || 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                </div>
              ) : (
                <div className="mt-2 text-xs text-slate-500">
                  No target probabilities returned.
                </div>
              )}
            </div>
          </div>
        ) : null}
      </section>

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
        <div className="fixed inset-0 z-[70] flex items-center justify-center pointer-events-none">
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
