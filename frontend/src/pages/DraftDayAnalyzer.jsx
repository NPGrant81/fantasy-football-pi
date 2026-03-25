import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchAllPlayers,
  fetchCurrentUser,
  fetchDraftHistory,
  fetchHistoricalRankings,
  fetchLeagueOwners,
  fetchLeagueSettings,
  fetchModelPredictions,
  fetchPlayerSeasonDetails,
  queryDraftAdvisor,
  runDraftSimulation,
} from '@api/draftAnalyzerApi';
import { normalizeApiError } from '@api/fetching';
import PlayerInsightCard from '@components/draft/insights/PlayerInsightCard';
import OwnerStrategyPanel from '@components/draft/insights/OwnerStrategyPanel';
import DraftDynamicsPanel from '@components/draft/insights/DraftDynamicsPanel';
import PlayerIdentityCard from '@components/player/PlayerIdentityCard';
import PageTemplate from '@components/layout/PageTemplate';
import { EmptyState, ErrorState, LoadingState } from '@components/common/AsyncState';
import {
  POSITION_CAPS,
  STRATEGY_MAX_SPEND_SHARE,
  normalizePos,
} from '@components/draft/insights/insightVocabulary';
import {
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  layerDrawer,
  modalCloseButton,
  modalOverlay,
  modalSurface,
  modalTitle,
} from '@utils/uiStandards';
import { FiX } from 'react-icons/fi';

const POSITION_FILTERS = ['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DEF'];
const SORTABLE_COLUMNS = ['name', 'team', 'position', 'value', 'price_min', 'price_avg', 'price_max', 'confidence'];
const UI_STATE_KEY = 'draftDayAnalyzer.uiState.v1';

const DEFAULT_UI_STATE = {
  selectedPlayerId: null,
  positionFilter: 'ALL',
  sortColumn: 'value',
  sortDirection: 'desc',
  searchQuery: '',
};

const rowHeight = 40;
const containerHeight = 560;

const PLACEHOLDER_NAME_PATTERNS = [/^generic\b/i, /^unknown\b/i, /^placeholder\b/i];

const parseNumber = (value, fallback = 0) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

const loadUiState = () => {
  if (typeof window === 'undefined') return DEFAULT_UI_STATE;
  try {
    const parsed = JSON.parse(localStorage.getItem(UI_STATE_KEY) || '{}');
    return {
      selectedPlayerId: parsed.selectedPlayerId ?? null,
      positionFilter: POSITION_FILTERS.includes(parsed.positionFilter)
        ? parsed.positionFilter
        : DEFAULT_UI_STATE.positionFilter,
      sortColumn: SORTABLE_COLUMNS.includes(parsed.sortColumn)
        ? parsed.sortColumn
        : DEFAULT_UI_STATE.sortColumn,
      sortDirection:
        parsed.sortDirection === 'asc' || parsed.sortDirection === 'desc'
          ? parsed.sortDirection
          : DEFAULT_UI_STATE.sortDirection,
      searchQuery:
        typeof parsed.searchQuery === 'string'
          ? parsed.searchQuery
          : DEFAULT_UI_STATE.searchQuery,
    };
  } catch {
    return DEFAULT_UI_STATE;
  }
};

function Drawer({ open, title, loading, error, children, onClose }) {
  return (
    <aside
      className={`fixed right-0 top-0 ${layerDrawer} h-screen w-full max-w-md transform border-l border-slate-700 bg-slate-950/95 shadow-2xl transition-transform duration-200 ${
        open ? 'translate-x-0' : 'translate-x-full'
      }`}
      inert={!open}
    >
      <div className="flex items-center justify-between border-b border-slate-800 p-4">
        <h3 className="text-sm font-black uppercase tracking-wider text-cyan-300">
          {title || 'Details'}
        </h3>
        <button
          type="button"
          className={buttonSecondary}
          onClick={onClose}
        >
          Close
        </button>
      </div>
      <div className="h-[calc(100vh-64px)] overflow-y-auto p-4 text-sm text-slate-300">
        {loading ? <LoadingState /> : null}
        {error ? <ErrorState message={error} /> : null}
        {!loading && !error ? children : null}
      </div>
    </aside>
  );
}

export default function DraftDayAnalyzer({ activeOwnerId, activeLeagueId }) {
  const [owners, setOwners] = useState([]);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [currentUserIsCommissioner, setCurrentUserIsCommissioner] = useState(false);
  const [players, setPlayers] = useState([]);
  const [history, setHistory] = useState([]);
  const [draftYear, setDraftYear] = useState(new Date().getFullYear());

  const [historicalRankings, setHistoricalRankings] = useState([]);
  const [rankingsLoading, setRankingsLoading] = useState(false);
  const [rankingsError, setRankingsError] = useState('');
  const [rankingsRefreshNonce, setRankingsRefreshNonce] = useState(0);

  const initialUi = useMemo(() => loadUiState(), []);
  const [selectedPlayerId, setSelectedPlayerId] = useState(
    initialUi.selectedPlayerId
  );
  const [positionFilter, setPositionFilter] = useState(initialUi.positionFilter);
  const [sortColumn, setSortColumn] = useState(initialUi.sortColumn);
  const [sortDirection, setSortDirection] = useState(initialUi.sortDirection);
  const [searchQuery, setSearchQuery] = useState(initialUi.searchQuery);

  const [scrollTop, setScrollTop] = useState(0);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState('');
  const [modelInsights, setModelInsights] = useState(null);

  const [simulationPerspectiveOwnerId, setSimulationPerspectiveOwnerId] =
    useState('');
  const [simulationIterations, setSimulationIterations] = useState(500);
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [simulationError, setSimulationError] = useState('');
  const [simulationResult, setSimulationResult] = useState(null);

  const [showPlayerInfoCard, setShowPlayerInfoCard] = useState(false);
  const [playerInfoLoading, setPlayerInfoLoading] = useState(false);
  const [playerInfoError, setPlayerInfoError] = useState('');
  const [playerInfoSeason, setPlayerInfoSeason] = useState(null);

  const [advisorMessage, setAdvisorMessage] = useState(null);
  const [advisorError, setAdvisorError] = useState('');
  const [advisorLoading, setAdvisorLoading] = useState(false);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTitle, setDrawerTitle] = useState('');
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerError, setDrawerError] = useState('');
  const [drawerContent, setDrawerContent] = useState(null);
  const [leaguePositionCaps, setLeaguePositionCaps] = useState(POSITION_CAPS);

  const listRef = useRef(null);

  useEffect(() => {
    const payload = {
      selectedPlayerId,
      positionFilter,
      sortColumn,
      sortDirection,
      searchQuery,
    };
    localStorage.setItem(UI_STATE_KEY, JSON.stringify(payload));
  }, [
    selectedPlayerId,
    positionFilter,
    sortColumn,
    sortDirection,
    searchQuery,
  ]);

  const rankingSeason = useMemo(() => Number(draftYear), [draftYear]);
  // Offset from the current calendar year (0 = this season, >0 = historical).
  // Used to differentiate "Pending data update" (current year) from "No data" (past years).
  const rankingSeasonOffset = useMemo(
    () => Math.max(0, new Date().getFullYear() - rankingSeason),
    [rankingSeason]
  );

  const fetchHistory = useCallback(async () => {
    if (!activeLeagueId || !draftYear) return;
    const sessionId = `LEAGUE_${activeLeagueId}_YEAR_${draftYear}`;
    try {
      const data = await fetchDraftHistory(sessionId);
      setHistory(Array.isArray(data) ? data : []);
    } catch {
      setHistory([]);
    }
  }, [activeLeagueId, draftYear]);

  useEffect(() => {
    if (!activeLeagueId) return;

    fetchCurrentUser()
      .then((data) => {
        setCurrentUserId(Number(data?.id || 0) || null);
        setCurrentUserIsCommissioner(Boolean(data?.is_commissioner));
      })
      .catch(() => {
        setCurrentUserId(null);
        setCurrentUserIsCommissioner(false);
      });

    fetchLeagueOwners(activeLeagueId)
      .then((data) => setOwners(Array.isArray(data) ? data : []))
      .catch(() => setOwners([]));

    fetchAllPlayers()
      .then((data) => setPlayers(Array.isArray(data) ? data : []))
      .catch(() => setPlayers([]));

    fetchLeagueSettings(activeLeagueId)
      .then((data) => {
        if (data?.draft_year) {
          setDraftYear(Number(data.draft_year));
        }
        const slots = data?.starting_slots || {};
        const caps = {
          QB: parseNumber(slots.MAX_QB, POSITION_CAPS.QB),
          RB: parseNumber(slots.MAX_RB, POSITION_CAPS.RB),
          WR: parseNumber(slots.MAX_WR, POSITION_CAPS.WR),
          TE: parseNumber(slots.MAX_TE, POSITION_CAPS.TE),
          DEF: parseNumber(slots.MAX_DEF, POSITION_CAPS.DEF),
          K: parseNumber(slots.MAX_K, POSITION_CAPS.K),
        };
        setLeaguePositionCaps(caps);
      })
      .catch(() => {});
  }, [activeLeagueId]);

  useEffect(() => {
    fetchHistory();
    const id = setInterval(fetchHistory, 4000);
    return () => clearInterval(id);
  }, [fetchHistory]);

  const availablePerspectiveOwners = useMemo(() => {
    if (currentUserIsCommissioner) {
      return owners;
    }
    if (!currentUserId) {
      return owners;
    }
    return owners.filter((owner) => Number(owner.id) === Number(currentUserId));
  }, [owners, currentUserId, currentUserIsCommissioner]);

  useEffect(() => {
    if (!activeLeagueId || !rankingSeason) return;
    setRankingsLoading(true);
    setRankingsError('');

    const rankingOwnerId = Number(
      simulationPerspectiveOwnerId || currentUserId || activeOwnerId || 0
    );

    fetchHistoricalRankings({
      season: rankingSeason,
      leagueId: activeLeagueId,
      ownerId: rankingOwnerId,
      limit: 300,
    })
      .then((data) => {
        setRankingsError('');
        setHistoricalRankings(Array.isArray(data) ? data : []);
      })
      .catch((error) => {
        setHistoricalRankings([]);
        setRankingsError(normalizeApiError(error, 'Unable to load historical rankings right now.'));
      })
      .finally(() => setRankingsLoading(false));
  }, [
    activeLeagueId,
    activeOwnerId,
    currentUserId,
    simulationPerspectiveOwnerId,
    rankingSeason,
    rankingsRefreshNonce,
  ]);

  useEffect(() => {
    if (availablePerspectiveOwners.length === 0) return;
    const current = String(simulationPerspectiveOwnerId || '');
    const stillValid = availablePerspectiveOwners.some(
      (owner) => String(owner.id) === current
    );
    if (stillValid) return;
    const fallback = String(
      currentUserId || activeOwnerId || availablePerspectiveOwners[0].id
    );
    setSimulationPerspectiveOwnerId(fallback);
  }, [
    availablePerspectiveOwners,
    simulationPerspectiveOwnerId,
    currentUserId,
    activeOwnerId,
  ]);

  const rankingByPlayerId = useMemo(() => {
    const map = new Map();
    historicalRankings.forEach((entry) => {
      map.set(Number(entry.player_id), entry);
    });
    return map;
  }, [historicalRankings]);

  const draftedPlayerIds = useMemo(
    () => new Set(history.map((pick) => Number(pick.player_id)).filter(Boolean)),
    [history]
  );

  const ownerStatsById = useMemo(() => {
    const stats = {};
    owners.forEach((owner) => {
      const picks = history.filter((pick) => Number(pick.owner_id) === owner.id);
      const spent = picks.reduce((sum, pick) => sum + parseNumber(pick.amount), 0);
      stats[owner.id] = {
        spent,
        picks: picks.length,
      };
    });
    return stats;
  }, [owners, history]);

  const enrichedPlayers = useMemo(() => {
    return players
      .filter((player) => !draftedPlayerIds.has(Number(player.id)))
      .filter((player) => {
        const name = String(player.name || '').trim();
        if (!name) return false;
        return !PLACEHOLDER_NAME_PATTERNS.some((pattern) => pattern.test(name));
      })
      .map((player) => {
        const ranking = rankingByPlayerId.get(Number(player.id));
        return {
          id: Number(player.id),
          name: player.name || 'Unknown',
          team: player.nfl_team || '-',
          position: normalizePos(player.position),
          // value = avg price from external sources when available, else model prediction
          value:
            ranking?.price_avg != null
              ? parseNumber(ranking.price_avg, 0)
              : ranking?.predicted_auction_value != null
                ? parseNumber(ranking.predicted_auction_value, 0)
                : null,
          price_min:
            ranking?.price_min != null ? parseNumber(ranking.price_min, 0) : null,
          price_avg:
            ranking?.price_avg != null ? parseNumber(ranking.price_avg, 0) : null,
          price_max:
            ranking?.price_max != null ? parseNumber(ranking.price_max, 0) : null,
          source_count: ranking?.source_count ?? 0,
          sources: ranking?.sources ?? [],
          confidence:
            ranking?.confidence_score == null
              ? null
              : parseNumber(ranking.confidence_score, 0),
          recommendation: ranking || null,
        };
      });
  }, [players, draftedPlayerIds, rankingByPlayerId]);

  const filteredPlayers = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return enrichedPlayers.filter((player) => {
      if (positionFilter !== 'ALL' && player.position !== positionFilter) {
        return false;
      }
      if (!query) return true;
      return (
        player.name.toLowerCase().includes(query) ||
        player.team.toLowerCase().includes(query) ||
        player.position.toLowerCase().includes(query)
      );
    });
  }, [enrichedPlayers, searchQuery, positionFilter]);

  const sortedPlayers = useMemo(() => {
    const direction = sortDirection === 'asc' ? 1 : -1;
    const rows = filteredPlayers.map((row, index) => ({ ...row, _stableIndex: index }));
    rows.sort((left, right) => {
      const a = left[sortColumn];
      const b = right[sortColumn];
      if (typeof a === 'number' && typeof b === 'number') {
        const primary = (a - b) * direction;
        if (primary !== 0) return primary;
      } else if (a == null && b != null) {
        return 1;
      } else if (a != null && b == null) {
        return -1;
      } else {
        const primary = String(a || '').localeCompare(String(b || '')) * direction;
        if (primary !== 0) return primary;
      }
      const byName = String(left.name || '').localeCompare(String(right.name || ''));
      if (byName !== 0) return byName;
      return left._stableIndex - right._stableIndex;
    });
    return rows.map(({ _stableIndex, ...row }) => row);
  }, [filteredPlayers, sortColumn, sortDirection]);

  useEffect(() => {
    if (!sortedPlayers.length) {
      setSelectedPlayerId(null);
      return;
    }
    const exists = sortedPlayers.some((player) => player.id === Number(selectedPlayerId));
    if (!exists) {
      setSelectedPlayerId(sortedPlayers[0].id);
    }
  }, [sortedPlayers, selectedPlayerId]);

  const selectedPlayer = useMemo(() => {
    return sortedPlayers.find((player) => player.id === Number(selectedPlayerId)) || null;
  }, [sortedPlayers, selectedPlayerId]);

  const comparisonCandidate = useMemo(() => {
    if (!selectedPlayer) return null;
    const targetPos = normalizePos(selectedPlayer.position);
    const targetOwner = Number(simulationPerspectiveOwnerId || activeOwnerId || 0);

    const teammatePickIds = new Set(
      history
        .filter((pick) => Number(pick.owner_id) === targetOwner)
        .map((pick) => Number(pick.player_id))
        .filter(Boolean)
    );

    const teammatePosIds = new Set(
      history
        .filter((pick) => Number(pick.owner_id) === targetOwner)
        .filter(
          (pick) =>
            normalizePos(
              pick.position || rankingByPlayerId.get(Number(pick.player_id))?.position
            ) === targetPos
        )
        .map((pick) => Number(pick.player_id))
        .filter(Boolean)
    );

    const rankedByValue = [...sortedPlayers].sort((a, b) => b.value - a.value);

    // Prefer same-position options that are not already on this owner's roster.
    return (
      rankedByValue.find(
        (player) =>
          Number(player.id) !== Number(selectedPlayer.id) &&
          normalizePos(player.position) === targetPos &&
          !teammatePosIds.has(Number(player.id)) &&
          !teammatePickIds.has(Number(player.id))
      ) ||
      rankedByValue.find((player) => Number(player.id) !== Number(selectedPlayer.id)) ||
      null
    );
  }, [
    selectedPlayer,
    simulationPerspectiveOwnerId,
    activeOwnerId,
    history,
    rankingByPlayerId,
    sortedPlayers,
  ]);

  const fallbackInsightRecommendation = useMemo(() => {
    if (!selectedPlayer || selectedPlayer.value == null) return null;

    const impliedRisk = Math.max(5, Math.min(95, 100 - parseNumber(selectedPlayer.confidence, 0)));
    const baseValue = parseNumber(selectedPlayer.value, 0);

    return {
      player_name: selectedPlayer.name,
      position: selectedPlayer.position,
      recommended_bid: baseValue,
      predicted_value: baseValue,
      risk_score: impliedRisk,
      value_score: baseValue,
      tier: baseValue >= 45 ? 'S' : baseValue >= 30 ? 'A' : baseValue >= 15 ? 'B' : 'C',
      flags: [],
    };
  }, [selectedPlayer]);

  const selectedInsightRecommendation = useMemo(() => {
    if (modelInsights?.recommendations?.length) {
      return modelInsights.recommendations[0];
    }
    return selectedPlayer?.recommendation || fallbackInsightRecommendation;
  }, [modelInsights, selectedPlayer, fallbackInsightRecommendation]);

  const activeInsightOwner = useMemo(() => {
    const targetOwnerId = Number(simulationPerspectiveOwnerId || activeOwnerId || 0);
    return owners.find((owner) => Number(owner.id) === targetOwnerId) || null;
  }, [owners, simulationPerspectiveOwnerId, activeOwnerId]);

  const activeInsightOwnerLabel = useMemo(() => {
    if (!activeInsightOwner) return null;
    return (
      activeInsightOwner.team_name ||
      activeInsightOwner.username ||
      `Owner ${activeInsightOwner.id}`
    );
  }, [activeInsightOwner]);

  const activeInsightOwnerIsCurrentUser = useMemo(() => {
    if (!activeInsightOwner || !currentUserId) return false;
    return Number(activeInsightOwner.id) === Number(currentUserId);
  }, [activeInsightOwner, currentUserId]);

  const draftDynamics = useMemo(() => {
    const ownerCount = owners.length;
    const availableByPosition = sortedPlayers.reduce((acc, player) => {
      const pos = normalizePos(player.position);
      acc[pos] = (acc[pos] || 0) + 1;
      return acc;
    }, {});

    const draftedByPosition = history.reduce((acc, pick) => {
      const pos = normalizePos(
        pick.position || rankingByPlayerId.get(Number(pick.player_id))?.position
      );
      if (!pos) return acc;
      acc[pos] = (acc[pos] || 0) + 1;
      return acc;
    }, {});

    const budgets = owners.map((owner) => {
      const spent = ownerStatsById[owner.id]?.spent || 0;
      const budget = parseNumber(owner.initial_budget || 200, 200);
      return Math.max(0, budget - spent);
    });

    const leagueAvgBudget =
      budgets.length > 0
        ? budgets.reduce((sum, b) => sum + b, 0) / budgets.length
        : 0;

    const budgetDistribution = owners
      .map((owner) => {
        const spent = ownerStatsById[owner.id]?.spent || 0;
        const budget = Math.max(0, parseNumber(owner.initial_budget || 200, 200) - spent);
        return {
          owner_id: owner.id,
          owner_name: owner.team_name || owner.username || `Owner ${owner.id}`,
          budget,
        };
      })
      .sort((a, b) => b.budget - a.budget);

    const byPositionDemand = Object.keys(leaguePositionCaps).map((position) => {
      const totalRequired = parseNumber(leaguePositionCaps[position], 0) * ownerCount;
      const alreadyDrafted = draftedByPosition[position] || 0;
      const remainingSlots = Math.max(0, totalRequired - alreadyDrafted);
      const availableCount = availableByPosition[position] || 0;
      const scarcity =
        remainingSlots > 0
          ? Math.min(100, (remainingSlots / Math.max(1, availableCount)) * 50)
          : 0;

      return {
        position,
        remainingSlots,
        availableCount,
        scarcity,
        replacementLevelValue: 0,
      };
    });

    return {
      inflationIndex: 1,
      leagueAvgBudget,
      remainingPlayers: sortedPlayers.length,
      draftedPlayers: draftedPlayerIds.size,
      budgetDistribution,
      byPositionDemand,
    };
  }, [
    owners,
    ownerStatsById,
    sortedPlayers,
    draftedPlayerIds.size,
    history,
    rankingByPlayerId,
    leaguePositionCaps,
  ]);

  const ownerStrategyInsights = useMemo(() => {
    const ownerId = Number(simulationPerspectiveOwnerId || 0);
    const owner = owners.find((row) => row.id === ownerId);
    if (!owner) return null;

    const ownerSpent = ownerStatsById[ownerId]?.spent || 0;
    const ownerBudget = parseNumber(owner.initial_budget || 200, 200);
    const ownerRemaining = Math.max(0, ownerBudget - ownerSpent);

    const positionalBalance = Object.keys(leaguePositionCaps).map((position) => ({
      position,
      owner: history.filter(
        (pick) =>
          Number(pick.owner_id) === ownerId &&
          normalizePos(pick.position || rankingByPlayerId.get(Number(pick.player_id))?.position) === position
      ).length,
      leagueAvg:
        owners.length > 0
          ? history.filter(
              (pick) =>
                normalizePos(
                  pick.position ||
                    rankingByPlayerId.get(Number(pick.player_id))?.position
                ) === position
            ).length / owners.length
          : 0,
      delta: 0,
    }));

    positionalBalance.forEach((row) => {
      row.delta = row.owner - row.leagueAvg;
    });

    const selectedPos = normalizePos(selectedInsightRecommendation?.position || selectedPlayer?.position);
    const positionSpend = history
      .filter(
        (pick) =>
          Number(pick.owner_id) === ownerId &&
          normalizePos(pick.position || rankingByPlayerId.get(Number(pick.player_id))?.position) === selectedPos
      )
      .reduce((sum, pick) => sum + parseNumber(pick.amount), 0);

    const posMaxSpend = ownerBudget * parseNumber(STRATEGY_MAX_SPEND_SHARE[selectedPos], 0.2);

    return {
      ownerStats: {
        budget: ownerRemaining,
        spent: ownerSpent,
        initialBudget: ownerBudget,
      },
      leagueAvgBudget: draftDynamics.leagueAvgBudget,
      positionalBalance,
      mostBehindPosition: [...positionalBalance].sort((a, b) => a.delta - b.delta)[0],
      aggressivenessIndex:
        draftDynamics.leagueAvgBudget > 0
          ? ownerRemaining / draftDynamics.leagueAvgBudget
          : 1,
      strategyAlignmentScore: 85,
      selectedPos,
      selectedPosSpend: positionSpend,
      posMaxSpend,
      exceedsPosCap:
        selectedInsightRecommendation?.recommended_bid != null &&
        positionSpend + Number(selectedInsightRecommendation.recommended_bid) > posMaxSpend,
    };
  }, [
    simulationPerspectiveOwnerId,
    owners,
    ownerStatsById,
    history,
    rankingByPlayerId,
    selectedInsightRecommendation,
    selectedPlayer,
    draftDynamics.leagueAvgBudget,
    leaguePositionCaps,
  ]);

  const virtualMeta = useMemo(() => {
    const total = sortedPlayers.length;
    const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - 3);
    const visibleCount = Math.ceil(containerHeight / rowHeight) + 6;
    const endIndex = Math.min(total, startIndex + visibleCount);
    return {
      startIndex,
      endIndex,
      topPad: startIndex * rowHeight,
      bottomPad: Math.max(0, (total - endIndex) * rowHeight),
      rows: sortedPlayers.slice(startIndex, endIndex),
    };
  }, [sortedPlayers, scrollTop]);

  const triggerModelInsights = useCallback(async () => {
    const ownerId = Number(
      simulationPerspectiveOwnerId || currentUserId || activeOwnerId || 0
    );
    const selectedId = Number(selectedPlayer?.id || 0);
    if (!ownerId || !selectedId || !activeLeagueId) return;

    setInsightsLoading(true);
    setInsightsError('');

    const payload = {
      owner_id: ownerId,
      season: Number(draftYear),
      league_id: Number(activeLeagueId),
      player_ids: [selectedId],
      limit: 1,
      model_version: 'current',
      draft_state: {
        drafted_player_ids: [...draftedPlayerIds],
      },
    };

    try {
      const data = await fetchModelPredictions(payload);
      setModelInsights(data || null);
    } catch (error) {
      setInsightsError(normalizeApiError(error, 'Unable to refresh model insights right now.'));
      setModelInsights(null);
    } finally {
      setInsightsLoading(false);
    }
  }, [
    simulationPerspectiveOwnerId,
    currentUserId,
    activeOwnerId,
    selectedPlayer,
    activeLeagueId,
    draftYear,
    draftedPlayerIds,
  ]);

  useEffect(() => {
    triggerModelInsights();
  }, [triggerModelInsights]);

  const runSimulation = useCallback(async () => {
    const focalOwnerId = Number(
      simulationPerspectiveOwnerId || currentUserId || activeOwnerId || 0
    );
    if (!focalOwnerId) {
      setSimulationError('Choose an owner perspective first.');
      return;
    }

    setSimulationLoading(true);
    setSimulationError('');
    setSimulationResult(null);

    try {
      const payload = {
        perspective_owner_id: focalOwnerId,
        iterations: Math.max(50, Math.min(10000, Number(simulationIterations) || 500)),
        seed: Number(draftYear),
        teams_count: Math.max(2, owners.length || 12),
      };
      const data = await runDraftSimulation(payload);
      setSimulationResult(data || null);
    } catch (error) {
      const detail = normalizeApiError(error, 'Simulation failed. Please try again.');
      setSimulationError(detail);
    } finally {
      setSimulationLoading(false);
    }
  }, [
    simulationPerspectiveOwnerId,
    currentUserId,
    activeOwnerId,
    simulationIterations,
    draftYear,
    owners.length,
  ]);

  const openPlayerInfo = useCallback(
    async (player) => {
      setSelectedPlayerId(player.id);
      setShowPlayerInfoCard(true);
      setPlayerInfoLoading(true);
      setPlayerInfoError('');
      setPlayerInfoSeason(null);

      try {
        const data = await fetchPlayerSeasonDetails(player.id, rankingSeason);
        setPlayerInfoSeason(data || null);
      } catch (error) {
        setPlayerInfoSeason(null);
        setPlayerInfoError(
          normalizeApiError(error, 'Unable to load player details right now.')
        );
      } finally {
        setPlayerInfoLoading(false);
      }
    },
    [rankingSeason]
  );

  const callAdvisorAction = useCallback(
    async (action) => {
      const playerId = Number(selectedPlayer?.id || 0) || null;
      const ownerId = Number(
        simulationPerspectiveOwnerId || currentUserId || activeOwnerId || 0
      );
      if (!ownerId || !activeLeagueId || !playerId) return;

      if (action === 'Simulate') {
        runSimulation();
        return;
      }

      if (action === 'Compare' && !comparisonCandidate) {
        setAdvisorError('No comparison candidate available right now.');
        return;
      }

      setAdvisorLoading(true);
      setAdvisorError('');
      setDrawerLoading(true);
      setDrawerError('');
      setDrawerOpen(true);
      setDrawerTitle(`${action} Details`);
      setDrawerContent(null);

      try {
        const question =
          action === 'Compare'
            ? `Compare ${selectedPlayer?.name || 'this player'} against ${comparisonCandidate?.name || 'the next best alternative'}.`
            : `Explain the recommendation and bidding strategy for ${selectedPlayer?.name || 'this player'}.`;

        const data = await queryDraftAdvisor({
          owner_id: ownerId,
          season: Number(draftYear),
          league_id: Number(activeLeagueId),
          player_id: playerId,
          compared_player_id:
            action === 'Compare' ? Number(comparisonCandidate?.id || 0) || null : null,
          question,
        });
        setAdvisorMessage(data || null);
        setDrawerContent(data || null);
      } catch (error) {
        const detail = normalizeApiError(error, 'Draft Day advisor request failed. Please retry.');
        setAdvisorError(detail);
        setDrawerError(detail);
      } finally {
        setAdvisorLoading(false);
        setDrawerLoading(false);
      }
    },
    [
      selectedPlayer,
      comparisonCandidate,
      simulationPerspectiveOwnerId,
      currentUserId,
      activeOwnerId,
      activeLeagueId,
      draftYear,
      runSimulation,
    ]
  );

  const toggleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortColumn(column);
    setSortDirection(column === 'name' ? 'asc' : 'desc');
  };

  const handleSearchChange = useCallback((event) => {
    const nextQuery = event.target.value;
    setSearchQuery(nextQuery);
    // New search should return to default ranking sort while preserving filter/year toggles.
    setSortColumn(DEFAULT_UI_STATE.sortColumn);
    setSortDirection(DEFAULT_UI_STATE.sortDirection);
    setScrollTop(0);
  }, []);

  return (
    <PageTemplate
      title="Draft Day Analyzer"
      subtitle="Dedicated strategy workspace with virtualized player rack, advisor, and simulation."
    >

      <section className={`${cardSurface} space-y-4`}>
        <div className="flex flex-wrap items-center gap-2">
          {POSITION_FILTERS.map((position) => (
            <button
              key={position}
              type="button"
              className={
                positionFilter === position ? buttonPrimary : buttonSecondary
              }
              onClick={() => setPositionFilter(position)}
            >
              {position}
            </button>
          ))}

          <input
            value={searchQuery}
            onChange={handleSearchChange}
            placeholder="Search players"
            className="ml-auto w-full max-w-sm rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
          />

          <button
            type="button"
            onClick={() => setRankingsRefreshNonce((n) => n + 1)}
            className={buttonSecondary}
            title="Refresh player rankings"
          >
            &#8635;
          </button>
        </div>

        {rankingsError ? <ErrorState message={rankingsError} className="text-xs" /> : null}

        <div className="rounded-lg border border-slate-800 bg-slate-950/70">
          <div className="grid grid-cols-12 border-b border-slate-800 px-3 py-2 text-xs font-bold uppercase tracking-wider text-slate-400">
            <button
              className="col-span-3 text-left"
              onClick={() => toggleSort('name')}
              type="button"
            >
              Name
            </button>
            <button
              className="col-span-2 text-left"
              onClick={() => toggleSort('team')}
              type="button"
            >
              Team
            </button>
            <button
              className="col-span-1 text-left"
              onClick={() => toggleSort('position')}
              type="button"
            >
              Pos
            </button>
            <button
              className="col-span-2 text-right"
              onClick={() => toggleSort('price_min')}
              type="button"
            >
              MIN $
            </button>
            <button
              className="col-span-2 text-right"
              onClick={() => toggleSort('price_avg')}
              type="button"
            >
              Avg $
            </button>
            <button
              className="col-span-2 text-right"
              onClick={() => toggleSort('price_max')}
              type="button"
            >
              MAX $
            </button>
          </div>

          <div
            ref={listRef}
            onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
            className="overflow-y-auto"
            style={{ height: `${containerHeight}px` }}
          >
            {rankingsLoading && !sortedPlayers.length ? (
              <div className="space-y-2 px-3 py-3" aria-label="Loading player rows">
                {Array.from({ length: 8 }).map((_, index) => (
                  <div
                    key={`skeleton-${index}`}
                    className="h-9 animate-pulse rounded border border-slate-800 bg-slate-900"
                  />
                ))}
              </div>
            ) : null}
            {rankingsLoading && sortedPlayers.length ? (
              <div className="px-3 py-2 text-xs text-slate-400" aria-live="polite">Refreshing player values...</div>
            ) : null}
            <div style={{ height: `${virtualMeta.topPad}px` }} />
            {virtualMeta.rows.map((player) => {
              const selected = player.id === Number(selectedPlayerId);
              return (
                <button
                  key={player.id}
                  type="button"
                  onClick={() => openPlayerInfo(player)}
                  className={`grid w-full grid-cols-12 px-3 py-2 text-left text-sm transition ${
                    selected
                      ? 'bg-cyan-950/30 text-cyan-200'
                      : 'text-slate-200 hover:bg-slate-900'
                  }`}
                  style={{ height: `${rowHeight}px` }}
                >
                  <span className="col-span-3 truncate">{player.name}</span>
                  <span className="col-span-2 truncate text-slate-400">{player.team}</span>
                  <span className="col-span-1 font-bold">{player.position}</span>
                  <span className="col-span-2 text-right text-slate-400">
                    {player.price_min == null ? '—' : `$${player.price_min.toFixed(0)}`}
                  </span>
                  <span className="col-span-2 text-right text-emerald-300">
                    {player.price_avg == null
                      ? rankingSeasonOffset === 0
                        ? 'Pending data update'
                        : 'No data'
                      : `$${player.price_avg.toFixed(0)}`}
                  </span>
                  <span className="col-span-2 text-right text-cyan-300">
                    {player.price_max == null ? '—' : `$${player.price_max.toFixed(0)}`}
                  </span>
                </button>
              );
            })}
            <div style={{ height: `${virtualMeta.bottomPad}px` }} />
            {!rankingsLoading && !sortedPlayers.length ? (
              <EmptyState
                message="No players found."
                className="px-3 py-6 text-center text-sm justify-center"
              />
            ) : null}
          </div>
        </div>

        <p className="text-xs text-slate-500">
          Showing {sortedPlayers.length} players. Virtualized list renders only
          visible rows for performance.
        </p>
      </section>

      <section className={`${cardSurface} space-y-3`}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-black uppercase tracking-wider text-emerald-300">
            Analyzer Insights
          </h2>
          <span className="text-xs text-slate-500">
            Selected: {selectedPlayer?.name || '-'}
          </span>
        </div>
        {insightsError ? <ErrorState message={insightsError} className="text-xs" /> : null}
        {insightsLoading ? (
          <LoadingState message="Refreshing model insights..." className="text-xs" />
        ) : null}

        <div className="grid gap-3 xl:grid-cols-3">
          <PlayerInsightCard recommendation={selectedInsightRecommendation} bidAmount={0} />
          <OwnerStrategyPanel
            insightOwnerId={Number(simulationPerspectiveOwnerId || 0)}
            insightOwnerLabel={activeInsightOwnerLabel}
            isCurrentUserOwner={activeInsightOwnerIsCurrentUser}
            ownerStrategyInsights={ownerStrategyInsights}
            recommendation={selectedInsightRecommendation}
          />
          <DraftDynamicsPanel draftDynamics={draftDynamics} />
        </div>
      </section>

      <section className={`${cardSurface} space-y-3`}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-black uppercase tracking-wider text-indigo-300">
            Draft Day Advisor
          </h2>
          <span className="text-xs text-slate-500">Alerts &amp; Simulation</span>
        </div>

        {advisorError ? <ErrorState message={advisorError} className="text-xs" /> : null}
        {advisorLoading ? (
          <LoadingState message="Updating advisor..." className="text-xs" />
        ) : null}

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={buttonSecondary}
            onClick={() => callAdvisorAction('Compare')}
            disabled={!comparisonCandidate || advisorLoading}
            title={
              comparisonCandidate
                ? `Compare against ${comparisonCandidate.name}`
                : 'No comparison candidate available'
            }
          >
            Compare
          </button>
          <button
            type="button"
            className={buttonSecondary}
            onClick={() => callAdvisorAction('Explain')}
            disabled={advisorLoading}
          >
            Explain
          </button>
          <button
            type="button"
            className={buttonPrimary}
            onClick={() => callAdvisorAction('Simulate')}
            disabled={simulationLoading}
          >
            Simulate
          </button>
        </div>

        {advisorMessage?.alerts?.length ? (
          <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-xs text-amber-300">
            {advisorMessage.alerts.map((alert, index) => (
              <div key={`${alert}-${index}`} className="border-t border-slate-800 py-1 first:border-t-0">
                {alert}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState message="No active alerts." className="text-xs" />
        )}

        <div className="border-t border-slate-800 pt-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-cyan-400">Perspective Simulation</p>
          <div className="grid gap-2 md:grid-cols-3">
            <label className="text-xs text-slate-400">
              Owner Perspective
              <select
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
                value={simulationPerspectiveOwnerId}
                onChange={(e) => setSimulationPerspectiveOwnerId(e.target.value)}
              >
                {availablePerspectiveOwners.map((owner) => (
                  <option key={owner.id} value={owner.id}>
                    {owner.team_name || owner.username || `Owner ${owner.id}`}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-xs text-slate-400">
              Iterations
              <input
                type="number"
                min="50"
                max="10000"
                value={simulationIterations}
                onChange={(e) => setSimulationIterations(e.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              />
            </label>

            <div className="flex items-end">
              <button
                type="button"
                className="w-full rounded border border-cyan-700 bg-cyan-950 px-3 py-2 text-xs font-black uppercase tracking-wide text-cyan-200"
                onClick={runSimulation}
                disabled={simulationLoading}
              >
                {simulationLoading ? 'Running...' : 'Run Simulation'}
              </button>
            </div>
          </div>
        </div>

        {simulationError ? <ErrorState message={simulationError} className="text-xs" /> : null}

        {simulationResult ? (
          <div className="space-y-4 pt-2">

            {/* ── TOP ROW: Summary metrics + Points distribution ── */}
            <div className="grid gap-4 md:grid-cols-2">

              {/* Focal Owner Summary */}
              {simulationResult.focal_owner_summary && (() => {
                const s = simulationResult.focal_owner_summary;
                const metrics = [
                  { label: 'Iterations', value: s.iterations, color: 'text-slate-200' },
                  { label: 'Exp. Points', value: s.expected_total_points != null ? s.expected_total_points.toFixed(1) : '—', color: 'text-emerald-300' },
                  { label: 'Pts Std Dev', value: s.points_stddev != null ? `±${s.points_stddev.toFixed(1)}` : '—', color: 'text-slate-400' },
                  { label: 'Exp. Spend', value: s.expected_total_spend != null ? `$${s.expected_total_spend.toFixed(0)}` : '—', color: 'text-amber-300' },
                  { label: 'Exp. Value Cap.', value: s.expected_value_captured != null ? s.expected_value_captured.toFixed(1) : '—', color: 'text-cyan-300' },
                ];
                const spend = [
                  { pos: 'QB', val: s.expected_spend_qb },
                  { pos: 'RB', val: s.expected_spend_rb },
                  { pos: 'WR', val: s.expected_spend_wr },
                  { pos: 'TE', val: s.expected_spend_te },
                  { pos: 'DEF', val: s.expected_spend_def },
                  { pos: 'K', val: s.expected_spend_k },
                ];
                return (
                  <div className="rounded-lg border border-slate-700 bg-slate-950/60 overflow-hidden">
                    <div className="bg-slate-900 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-400 border-b border-slate-700">
                      Focal Owner Summary
                    </div>
                    <div className="grid grid-cols-5 divide-x divide-slate-800 border-b border-slate-800">
                      {metrics.map(({ label, value, color }) => (
                        <div key={label} className="flex flex-col items-center py-2 px-1 gap-0.5">
                          <span className={`text-sm font-black ${color}`}>{value}</span>
                          <span className="text-[9px] uppercase text-slate-500 text-center leading-tight">{label}</span>
                        </div>
                      ))}
                    </div>
                    <div className="grid grid-cols-6 divide-x divide-slate-800">
                      {spend.map(({ pos, val }) => (
                        <div key={pos} className="flex flex-col items-center py-2 px-1 gap-0.5">
                          <span className="text-xs font-bold text-indigo-300">
                            {val != null ? `$${val.toFixed(0)}` : '—'}
                          </span>
                          <span className="text-[9px] uppercase text-slate-500">{pos}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* Points Distribution */}
              {simulationResult.focal_points_distribution && (() => {
                const d = simulationResult.focal_points_distribution;
                const rows = [
                  { label: 'P10 (Floor)', val: d.points_p10, color: 'text-red-400' },
                  { label: 'P25', val: d.points_p25, color: 'text-orange-300' },
                  { label: 'P50 (Median)', val: d.points_p50, color: 'text-yellow-300' },
                  { label: 'P75', val: d.points_p75, color: 'text-lime-300' },
                  { label: 'P90 (Ceiling)', val: d.points_p90, color: 'text-emerald-300' },
                ];
                return (
                  <div className="rounded-lg border border-slate-700 bg-slate-950/60 overflow-hidden">
                    <div className="bg-slate-900 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-400 border-b border-slate-700">
                      Points Distribution
                    </div>
                    <div className="divide-y divide-slate-800/60">
                      {rows.map(({ label, val, color }) => (
                        <div key={label} className="flex items-center justify-between px-4 py-1.5">
                          <span className="text-xs text-slate-400">{label}</span>
                          <span className={`text-sm font-black tabular-nums ${color}`}>
                            {val != null ? Number(val).toFixed(1) : '—'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* ── KEY TARGETS TABLE ── */}
            {Array.isArray(simulationResult.key_target_probabilities) && simulationResult.key_target_probabilities.length > 0 && (
              <div className="rounded-lg border border-slate-700 bg-slate-950/60 overflow-hidden">
                <div className="bg-slate-900 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-400 border-b border-slate-700">
                  Key Target Probabilities
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-left text-[10px] uppercase tracking-wider text-slate-500">
                        <th className="px-3 py-2">Player</th>
                        <th className="px-3 py-2 text-center w-12">Pos</th>
                        <th className="px-3 py-2 text-right w-20">Exp. Value</th>
                        <th className="px-3 py-2 text-right w-20">Avg Bid</th>
                        <th className="px-3 py-2 text-right w-16">% Win</th>
                        <th className="px-3 py-2 text-left">Top Rival Bidders</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {simulationResult.key_target_probabilities.map((row) => {
                        const prob = row.probability * 100;
                        const probColor = prob >= 50 ? 'text-emerald-300' : prob >= 25 ? 'text-yellow-300' : 'text-red-400';
                        const rivals = Array.isArray(row.rival_bidders) ? row.rival_bidders : [];
                        return (
                          <tr key={row.player_id} className="hover:bg-slate-900/60 transition-colors">
                            <td className="px-3 py-2 font-semibold text-slate-100 truncate max-w-[140px]">
                              {row.player_name}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <span className="rounded px-1.5 py-0.5 text-[10px] font-bold bg-slate-800 text-cyan-300 uppercase">
                                {row.position || '—'}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-right font-bold text-emerald-300 tabular-nums">
                              {row.predicted_auction_value > 0 ? `$${Number(row.predicted_auction_value).toFixed(0)}` : '—'}
                            </td>
                            <td className="px-3 py-2 text-right text-amber-300 tabular-nums">
                              {row.avg_bid > 0 ? `$${Number(row.avg_bid).toFixed(0)}` : '—'}
                            </td>
                            <td className={`px-3 py-2 text-right font-black tabular-nums ${probColor}`}>
                              {prob.toFixed(0)}%
                            </td>
                            <td className="px-3 py-2">
                              {rivals.length === 0 ? (
                                <span className="text-slate-600">—</span>
                              ) : (
                                <div className="flex flex-wrap gap-1">
                                  {rivals.map((rival) => (
                                    <span
                                      key={rival.owner_id}
                                      title={`Won in ${rival.win_count} sim iteration(s)`}
                                      className="rounded-full bg-slate-800 border border-slate-700 px-2 py-0.5 text-[10px] text-slate-300"
                                    >
                                      {rival.owner_name}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </section>

      <Drawer
        open={drawerOpen}
        title={drawerTitle}
        loading={drawerLoading}
        error={drawerError}
        onClose={() => setDrawerOpen(false)}
      >
        {drawerContent ? (
          <pre className="whitespace-pre-wrap break-words rounded border border-slate-800 bg-slate-900 p-3 text-xs">
            {JSON.stringify(drawerContent, null, 2)}
          </pre>
        ) : (
          <EmptyState message="No details loaded yet." />
        )}
      </Drawer>

      {showPlayerInfoCard ? (
        <div className={`${modalOverlay} pointer-events-none`}>
          <div className={`${modalSurface} pointer-events-auto max-w-3xl p-6`}>
            <div className="mb-5 flex items-center justify-between">
              <h3 className={`${modalTitle} mb-0 w-full justify-center text-center`}>
                Player Info Card
              </h3>
              <button
                type="button"
                onClick={() => setShowPlayerInfoCard(false)}
                className={modalCloseButton}
              >
                <FiX />
              </button>
            </div>

            {playerInfoLoading ? (
              <div className="py-10 text-center">
                <LoadingState
                  message="Loading player details..."
                  className="justify-center"
                />
              </div>
            ) : playerInfoError ? (
              <ErrorState message={playerInfoError} className="rounded-md" />
            ) : selectedPlayer ? (
              <div className="space-y-4">
                <PlayerIdentityCard
                  playerName={playerInfoSeason?.player_name || selectedPlayer.name}
                  position={playerInfoSeason?.position || selectedPlayer.position}
                  nflTeam={playerInfoSeason?.nfl_team || selectedPlayer.team}
                  headshotUrl={playerInfoSeason?.headshot_url || ''}
                  teamLogoUrl={playerInfoSeason?.team_logo_url || ''}
                />

                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <div className="rounded-lg border border-slate-700 bg-slate-950/70 p-3">
                    <div className="text-[10px] uppercase text-slate-500">Season</div>
                    <div className="text-lg font-black text-slate-100">{rankingSeason}</div>
                  </div>
                  <div className="rounded-lg border border-slate-700 bg-slate-950/70 p-3">
                    <div className="text-[10px] uppercase text-slate-500">Value</div>
                    <div className="text-lg font-black text-emerald-300">
                      {selectedPlayer.value == null
                        ? rankingSeasonOffset === 0
                          ? 'Pending'
                          : 'N/A'
                        : `$${Number(selectedPlayer.value).toFixed(1)}`}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-700 bg-slate-950/70 p-3">
                    <div className="text-[10px] uppercase text-slate-500">Confidence</div>
                    <div className="text-lg font-black text-indigo-300">
                      {selectedPlayer.confidence == null
                        ? '--'
                        : `${Number(selectedPlayer.confidence).toFixed(1)}%`}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-700 bg-slate-950/70 p-3">
                    <div className="text-[10px] uppercase text-slate-500">Tier</div>
                    <div className="text-lg font-black text-cyan-300">
                      {selectedPlayer.recommendation?.consensus_tier || '--'}
                    </div>
                  </div>
                </div>

                <div className="rounded-md border border-slate-800 bg-slate-950/70 p-3 text-xs text-slate-300">
                  <div className="mb-1 text-slate-500">Valuation Details</div>
                  <div>Final Score: {Number(selectedPlayer.recommendation?.final_score || 0).toFixed(2)}</div>
                  <div>
                    Predicted Auction Value: ${Number(selectedPlayer.recommendation?.predicted_auction_value || 0).toFixed(2)}
                  </div>
                  <div>
                    Value Over Replacement: {Number(selectedPlayer.recommendation?.value_over_replacement || 0).toFixed(2)}
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState message="No player selected." className="text-sm" />
            )}
          </div>
        </div>
      ) : null}
    </PageTemplate>
  );
}
