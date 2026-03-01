import { useEffect, useState, useMemo, useCallback } from 'react';
import {
  FiAlertTriangle,
  FiTrendingUp,
  FiRepeat,
  FiBell,
  FiPlus,
  FiList,
  FiSend,
  FiX,
  FiBarChart2,
} from 'react-icons/fi';
import { Link } from 'react-router-dom';
// --- Commissioner Modal Imports ---
import ScoringRulesModal from '../commissioner/components/ScoringRulesModal';
import WaiverWireRulesModal from '../commissioner/components/WaiverWireRulesModal';
import TradeRulesModal from '../commissioner/components/TradeRulesModal';
import PlayerIdentityCard from '../../components/player/PlayerIdentityCard';

// Professional Imports
import apiClient from '@api/client';
import LeagueAdvisor from '../../components/LeagueAdvisor';
import Toast from '../../components/Toast';
import {
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  inputBase,
  modalCloseButton,
  modalOverlay,
  modalSurface,
  modalTitle,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '@utils/uiStandards';

// --- 1.1 CONSTANTS & HELPERS (Outside Render) ---
const POS_RANK = { QB: 1, RB: 2, WR: 3, TE: 4, DEF: 5, K: 6, FLEX: 7 };
const FLEX_SLOT_LABEL = 'FLEX (RB/WR/TE)';
const FLEX_NOT_ENOUGH_ERROR = 'not enough FLEX (needs extra RB/WR/TE starter)';
const FLEX_TOO_MANY_ERROR = 'too many FLEX-eligible starters (RB/WR/TE)';
const DEFAULT_STARTER_SLOTS = {
  QB: 1,
  RB: 2,
  WR: 2,
  TE: 1,
  DEF: 1,
  K: 1,
  FLEX: 1,
};

const MIN_ACTIVE_REQUIREMENTS = {
  QB: 1,
  RB: 1,
  WR: 1,
  TE: 1,
  K: 0,
  DEF: 1,
};

const DEFAULT_MAX_POSITION_LIMITS = {
  QB: 3,
  RB: 5,
  WR: 5,
  TE: 3,
  K: 1,
  DEF: 1,
};

const clampInt = (value, min, max) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return min;
  return Math.max(min, Math.min(max, Math.trunc(parsed)));
};

const normalizePosition = (position) => {
  if (position === 'TD' || position === 'DST') return 'DEF';
  return position;
};

const toProjectedPoints = (player) => {
  const value = Number(
    player?.projected_points ?? player?.proj_score ?? player?.projected ?? 0
  );
  return Number.isFinite(value) ? value : 0;
};

const normalizeStartingSlots = (slots) => {
  const merged = { ...DEFAULT_STARTER_SLOTS };
  if (!slots || typeof slots !== 'object') return merged;

  for (const [key, value] of Object.entries(slots)) {
    const normalizedKey = String(key).toUpperCase();
    if (Object.hasOwn(merged, normalizedKey)) {
      const parsed = Number(value);
      merged[normalizedKey] =
        Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
    }
  }

  return merged;
};

const getSlotLabel = (position) =>
  position === 'FLEX' ? FLEX_SLOT_LABEL : position;

const getPlayerSlotLabel = (player) =>
  getSlotLabel(player?.slot_assigned || normalizePosition(player?.position));

const buildWeeklyStartSitPlan = (roster, week, starterSlots) => {
  const slots = normalizeStartingSlots(starterSlots);
  const players = (Array.isArray(roster) ? roster : []).map((player) => ({
    ...player,
    position: normalizePosition(player.position),
    projected_for_week: toProjectedPoints(player),
    bye_week: player.bye_week ?? null,
  }));

  const byePlayers = [];
  const availablePlayers = [];

  for (const player of players) {
    if (player.bye_week && Number(player.bye_week) === Number(week)) {
      byePlayers.push(player);
    } else {
      availablePlayers.push(player);
    }
  }

  const pools = {
    QB: availablePlayers
      .filter((p) => p.position === 'QB')
      .sort((a, b) => b.projected_for_week - a.projected_for_week),
    RB: availablePlayers
      .filter((p) => p.position === 'RB')
      .sort((a, b) => b.projected_for_week - a.projected_for_week),
    WR: availablePlayers
      .filter((p) => p.position === 'WR')
      .sort((a, b) => b.projected_for_week - a.projected_for_week),
    TE: availablePlayers
      .filter((p) => p.position === 'TE')
      .sort((a, b) => b.projected_for_week - a.projected_for_week),
    DEF: availablePlayers
      .filter((p) => p.position === 'DEF')
      .sort((a, b) => b.projected_for_week - a.projected_for_week),
    K: availablePlayers
      .filter((p) => p.position === 'K')
      .sort((a, b) => b.projected_for_week - a.projected_for_week),
  };

  const selectedIds = new Set();
  const starters = [];
  const actualSlotCounts = {};

  for (const [position, slotCount] of Object.entries(slots)) {
    if (position === 'FLEX' || slotCount <= 0) continue;

    const pool = pools[position] || [];
    for (let index = 0; index < slotCount && index < pool.length; index += 1) {
      starters.push({ ...pool[index], slot_assigned: position });
      selectedIds.add(pool[index].id);
      actualSlotCounts[position] = (actualSlotCounts[position] || 0) + 1;
    }
  }

  const flexPool = [
    ...(pools.RB || []),
    ...(pools.WR || []),
    ...(pools.TE || []),
  ]
    .filter((player) => !selectedIds.has(player.id))
    .sort((a, b) => b.projected_for_week - a.projected_for_week);

  const flexSlots = slots.FLEX || 0;
  for (
    let flexIndex = 0;
    flexIndex < flexSlots && flexIndex < flexPool.length;
    flexIndex += 1
  ) {
    starters.push({
      ...flexPool[flexIndex],
      slot_assigned: 'FLEX',
      display_position: `${normalizePosition(flexPool[flexIndex].position)} • ${FLEX_SLOT_LABEL}`,
    });
    selectedIds.add(flexPool[flexIndex].id);
    actualSlotCounts.FLEX = (actualSlotCounts.FLEX || 0) + 1;
  }

  const sits = availablePlayers.filter((player) => !selectedIds.has(player.id));

  const totalRequired = Object.values(slots).reduce(
    (sum, count) => sum + Number(count || 0),
    0
  );

  const validationErrors = [];
  if (starters.length < totalRequired)
    validationErrors.push('not enough players');
  if (starters.length > totalRequired)
    validationErrors.push('too many players');

  for (const [position, requiredCount] of Object.entries(slots)) {
    const required = Number(requiredCount || 0);
    if (required <= 0) continue;
    const actual = Number(actualSlotCounts[position] || 0);
    if (actual < required) {
      validationErrors.push(
        position === 'FLEX' ? FLEX_NOT_ENOUGH_ERROR : `not enough ${position}`
      );
    }
    if (actual > required) {
      validationErrors.push(
        position === 'FLEX' ? FLEX_TOO_MANY_ERROR : `too many ${position}`
      );
    }
  }

  return {
    starters,
    sits,
    byePlayers,
    slots,
    totalRequired,
    actualSlotCounts,
    validationErrors,
  };
};

const sortRosterByHierarchy = (players) => {
  return [...(players || [])].sort((left, right) => {
    const leftPos = normalizePosition(left.position);
    const rightPos = normalizePosition(right.position);
    const positionDiff = (POS_RANK[leftPos] || 99) - (POS_RANK[rightPos] || 99);
    if (positionDiff !== 0) return positionDiff;
    const projDiff = toProjectedPoints(right) - toProjectedPoints(left);
    if (projDiff !== 0) return projDiff;
    return String(left.name || '').localeCompare(String(right.name || ''));
  });
};

export default function MyTeam({ activeOwnerId }) {
  const viewedOwnerId = activeOwnerId ? Number(activeOwnerId) : null;
  // --- 0.1 Commissioner Modal State ---
  const [showScoring, setShowScoring] = useState(false);
  const [showWaivers, setShowWaivers] = useState(false);
  const [showTrades, setShowTrades] = useState(false);
  const [showRuleViewer, setShowRuleViewer] = useState(false);
  const [ruleViewerType, setRuleViewerType] = useState('scoring');
  const [showProposeTrade, setShowProposeTrade] = useState(false);
  const [leagueOwners, setLeagueOwners] = useState([]);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [myTradeRoster, setMyTradeRoster] = useState([]);
  const [targetRoster, setTargetRoster] = useState([]);
  const [proposalToUserId, setProposalToUserId] = useState('');
  const [offeredPlayerId, setOfferedPlayerId] = useState('');
  const [requestedPlayerId, setRequestedPlayerId] = useState('');
  const [proposalNote, setProposalNote] = useState('');
  const [offeredDollars, setOfferedDollars] = useState('');
  const [requestedDollars, setRequestedDollars] = useState('');
  const [toast, setToast] = useState(null);
  const [showPlayerPerformance, setShowPlayerPerformance] = useState(false);
  const [showLineupValidationModal, setShowLineupValidationModal] =
    useState(false);
  const [draggingPlayerId, setDraggingPlayerId] = useState(null);
  const [submittingRoster, setSubmittingRoster] = useState(false);
  const [lineupSubmittedForWeek, setLineupSubmittedForWeek] = useState(false);
  const [baselineLineupStatus, setBaselineLineupStatus] = useState({});
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [playerPerformance, setPlayerPerformance] = useState(null);
  const [playerPerformanceLoading, setPlayerPerformanceLoading] =
    useState(false);
  // --- USER/LEAGUE CONTEXT ---
  const [userInfo, setUserInfo] = useState({
    username: '',
    leagueName: '',
    leagueId: null,
    draftStatus: 'PRE_DRAFT',
    is_commissioner: false,
  });
  const [scoringRules, setScoringRules] = useState([]);
  const [starterRequirements, setStarterRequirements] = useState(
    DEFAULT_STARTER_SLOTS
  );
  const [activeRosterRequired, setActiveRosterRequired] = useState(9);
  const [maxPositionLimits, setMaxPositionLimits] = useState(
    DEFAULT_MAX_POSITION_LIMITS
  );
  const [allowPartialLineup, setAllowPartialLineup] = useState(false);
  const [summary, setSummary] = useState(null);
  const [waiverDeadlineSetting, setWaiverDeadlineSetting] = useState(null);
  const [tradeDeadlineSetting, setTradeDeadlineSetting] = useState(null);

  const [viewMode, setViewMode] = useState('actual'); // 'actual' or 'recommended'
  const [recState, setRecState] = useState([]); // recommended lineup state

  // accordion expansion state for active lineup positions
  const [expandedPositions, setExpandedPositions] = useState(new Set());

  const togglePosition = useCallback((pos) => {
    setExpandedPositions((prev) => {
      const next = new Set(prev);
      if (next.has(pos)) next.delete(pos);
      else next.add(pos);
      return next;
    });
  }, []);

  const computeRemaining = (iso) => {
    if (!iso) return '';
    const then = Date.parse(iso);
    if (isNaN(then)) return '';
    const diff = then - Date.now();
    if (diff <= 0) return '';
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hrs = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    return `${days}d ${hrs}h REMAINING`;
  };

  const waiverRemaining = computeRemaining(waiverDeadlineSetting);
  const tradeRemaining = computeRemaining(tradeDeadlineSetting);
  useEffect(() => {
    async function fetchUserLeague() {
      try {
        const userRes = await apiClient.get('/auth/me');
        const loggedInUserId = Number(userRes.data.user_id);
        let leagueName = '';
        let leagueId = userRes.data.league_id;
        let draftStatus = 'PRE_DRAFT';
        let is_commissioner = userRes.data.is_commissioner;
        setCurrentUserId(loggedInUserId);
        if (leagueId) {
          const leagueRes = await apiClient.get(`/leagues/${leagueId}`);
          leagueName = leagueRes.data.name;
          draftStatus = leagueRes.data.draft_status || 'PRE_DRAFT';

          try {
            const ownersRes = await apiClient.get(
              `/leagues/owners?league_id=${leagueId}`
            );
            setLeagueOwners(ownersRes.data || []);
          } catch {
            setLeagueOwners([]);
          }

          try {
            const settingsRes = await apiClient.get(
              `/leagues/${leagueId}/settings`
            );
            const slots = settingsRes.data.starting_slots || {};
            setScoringRules(settingsRes.data.scoring_rules || []);
            setWaiverDeadlineSetting(settingsRes.data.waiver_deadline || null);
            setTradeDeadlineSetting(settingsRes.data.trade_deadline || null);
            setStarterRequirements(normalizeStartingSlots(slots));
            setActiveRosterRequired(
              clampInt(slots.ACTIVE_ROSTER_SIZE ?? 9, 5, 12)
            );
            setMaxPositionLimits({
              QB: clampInt(slots.MAX_QB ?? 3, 1, 3),
              RB: clampInt(slots.MAX_RB ?? 5, 1, 5),
              WR: clampInt(slots.MAX_WR ?? 5, 1, 5),
              TE: clampInt(slots.MAX_TE ?? 3, 1, 3),
              K: clampInt(slots.MAX_K ?? 1, 0, 1),
              DEF: 1,
            });
            setAllowPartialLineup(
              Number(slots.ALLOW_PARTIAL_LINEUP ?? 0) === 1
            );
          } catch {
            setScoringRules([]);
            setStarterRequirements(DEFAULT_STARTER_SLOTS);
            setActiveRosterRequired(9);
            setMaxPositionLimits(DEFAULT_MAX_POSITION_LIMITS);
            setAllowPartialLineup(false);
          }
        }
        setUserInfo({
          username: userRes.data.username,
          leagueName,
          leagueId,
          draftStatus,
          is_commissioner,
        });
        // Fetch dashboard summary for locker room
        const summaryOwnerId = viewedOwnerId || loggedInUserId;
        if (summaryOwnerId) {
          const dashRes = await apiClient.get(`/dashboard/${summaryOwnerId}`);
          setSummary(dashRes.data);
        }

        if (!loggedInUserId) {
          setMyTradeRoster([]);
        } else {
          try {
            const myDashRes = await apiClient.get(
              `/dashboard/${loggedInUserId}`
            );
            setMyTradeRoster(
              Array.isArray(myDashRes.data?.roster) ? myDashRes.data.roster : []
            );
          } catch {
            setMyTradeRoster([]);
          }
        }
      } catch {
        setCurrentUserId(null);
        setUserInfo({
          username: '',
          leagueName: '',
          leagueId: null,
          draftStatus: 'PRE_DRAFT',
          is_commissioner: false,
        });
        setScoringRules([]);
        setStarterRequirements(DEFAULT_STARTER_SLOTS);
        setActiveRosterRequired(9);
        setMaxPositionLimits(DEFAULT_MAX_POSITION_LIMITS);
        setAllowPartialLineup(false);
        setSummary(null);
        setMyTradeRoster([]);
        setLeagueOwners([]);
      }
    }
    fetchUserLeague();
  }, [viewedOwnerId]);

  useEffect(() => {
    async function loadTargetRoster() {
      if (!proposalToUserId) {
        setTargetRoster([]);
        setRequestedPlayerId('');
        return;
      }

      try {
        const res = await apiClient.get(`/dashboard/${proposalToUserId}`);
        console.log('loaded target roster for', proposalToUserId, res.data);
        setTargetRoster(Array.isArray(res.data?.roster) ? res.data.roster : []);
      } catch (err) {
        console.error('failed to load target roster', err);
        setTargetRoster([]);
      }
    }

    loadTargetRoster();
  }, [proposalToUserId]);
  // --- 1.2 STATE MANAGEMENT ---
  const [teamData, setTeamData] = useState(null);
  const [rosterState, setRosterState] = useState([]);
  const [selectedWeek, setSelectedWeek] = useState(1);

  // weeklyPlan always derives from the actual roster state (used for both display and
  // initializing recommended view).  We swap to recState manually when rendering
  // the recommended view rather than making weeklyPlan depend on recState, which
  // would create circular updates.
  const weeklyPlan = useMemo(
    () =>
      buildWeeklyStartSitPlan(rosterState, selectedWeek, starterRequirements),
    [rosterState, selectedWeek, starterRequirements]
  );

  // initialize recommended state when entering recommended view or when the
  // underlying roster/plan changes.  We deliberately compute from weeklyPlan
  // (which uses the actual roster) so that recState is seeded correctly and
  // does not later force an update cycle.
  useEffect(() => {
    if (viewMode !== 'recommended') return;
    const starts = (weeklyPlan.starters || []).map((p) => ({
      ...p,
      status: 'STARTER',
    }));
    const sits = [
      ...(weeklyPlan.sits || []),
      ...(weeklyPlan.byePlayers || []),
    ].map((p) => ({ ...p, status: 'BENCH' }));
    setRecState([...starts, ...sits]);
  }, [viewMode, weeklyPlan.starters, weeklyPlan.sits, weeklyPlan.byePlayers]);
  const [startSitSort, setStartSitSort] = useState('position');
  // FIX: Start loading as true to avoid sync setState inside useEffect
  const [loading, setLoading] = useState(true);
  const canProposeTrade =
    !!currentUserId && (!viewedOwnerId || viewedOwnerId === currentUserId);

  // --- 1.3 DATA RETRIEVAL (The Engine) ---
  const fetchTeam = useCallback(() => {
    if (activeOwnerId) {
      // apiClient handles the Base URL and the token automatically via interceptors
      apiClient
        .get(`/team/${activeOwnerId}?week=${selectedWeek}`)
        .then((res) => {
          setTeamData(res.data);
          setLineupSubmittedForWeek(Boolean(res.data?.lineup_submitted));
          const roster = Array.isArray(res.data.players)
            ? res.data.players
            : Array.isArray(res.data.roster)
              ? res.data.roster
              : [];
          const processedRoster = roster.map((p) => ({
            ...p,
            status: p.status || 'BENCH',
            player_id: p.player_id || p.id,
            position: normalizePosition(p.position),
            position_rank: POS_RANK[normalizePosition(p.position)] || 99,
          }));
          setRosterState(processedRoster);
          const baseline = {};
          processedRoster.forEach((player) => {
            baseline[String(player.player_id)] = player.status || 'BENCH';
          });
          setBaselineLineupStatus(baseline);
        })
        .catch((err) => {
          setRosterState([]);
          console.error('Roster fetch failed', err);
        })
        .finally(() => setLoading(false));
    }
  }, [activeOwnerId, selectedWeek]);

  useEffect(() => {
    fetchTeam();
  }, [fetchTeam]);

  // --- 1.4 UTILITIES & DERIVED STATE ---
  const weekOptions = useMemo(
    () => Array.from({ length: 18 }, (_, index) => index + 1),
    []
  );

  const sortByPreference = useCallback(
    (players) => {
      const list = [...players];
      if (startSitSort === 'position') {
        return list.sort((left, right) => {
          const leftPos = normalizePosition(left.position).split('/')[0];
          const rightPos = normalizePosition(right.position).split('/')[0];
          const positionDiff =
            (POS_RANK[leftPos] || 99) - (POS_RANK[rightPos] || 99);
          if (positionDiff !== 0) return positionDiff;
          return right.projected_for_week - left.projected_for_week;
        });
      }
      return list.sort(
        (left, right) => right.projected_for_week - left.projected_for_week
      );
    },
    [startSitSort]
  );

  // depending on viewMode we either use the weekly plan computed from the
  // actual roster or the user-modifiable recState when in "recommended" mode.
  const sortedStartRecommendations = useMemo(() => {
    if (viewMode === 'recommended') {
      return sortByPreference(recState.filter((p) => p.status === 'STARTER'));
    }
    return sortByPreference(weeklyPlan.starters);
  }, [viewMode, recState, weeklyPlan.starters, sortByPreference]);

  const sortedSitRecommendations = useMemo(() => {
    if (viewMode === 'recommended') {
      return sortByPreference(recState.filter((p) => p.status === 'SIT'));
    }
    return sortByPreference(weeklyPlan.sits);
  }, [viewMode, recState, weeklyPlan.sits, sortByPreference]);

  // bye players are always based on the actual weekly plan
  const byePlayers = weeklyPlan.byePlayers;

  const lineupRuleSnapshot = useMemo(() => {
    // ignore any taxi players when evaluating starters; they are never
    // eligible for the active lineup and should not cause validation errors.
    const currentStarters = rosterState.filter(
      (player) => player.status === 'STARTER' && !player.is_taxi
    );
    const counts = { QB: 0, RB: 0, WR: 0, TE: 0, DEF: 0, K: 0 };

    for (const player of currentStarters) {
      const position = normalizePosition(player.position);
      if (Object.hasOwn(counts, position)) {
        counts[position] += 1;
      }
    }

    const errors = [];
    if (currentStarters.length < activeRosterRequired && !allowPartialLineup) {
      errors.push('not enough players');
    }
    if (currentStarters.length > activeRosterRequired) {
      errors.push('too many players');
    }

    const tierRows = Object.keys(MIN_ACTIVE_REQUIREMENTS)
      .filter((position) => {
        const minimum = Number(starterRequirements[position] ?? 0);
        const maximum = Number(
          maxPositionLimits[position] ?? DEFAULT_MAX_POSITION_LIMITS[position]
        );
        return minimum > 0 || maximum > 0;
      })
      .map((position) => {
        const minimum = Number(starterRequirements[position] ?? 0);
        const maximum = Number(
          maxPositionLimits[position] ?? DEFAULT_MAX_POSITION_LIMITS[position]
        );
        const actual = Number(counts[position] || 0);
        const meetsMin = actual >= minimum;
        const meetsMax = actual <= maximum;

        if (minimum > 0 && !meetsMin && !allowPartialLineup)
          errors.push(`not enough ${position}`);
        if (maximum >= 0 && !meetsMax) errors.push(`too many ${position}`);

        return {
          position,
          minimum,
          maximum,
          actual,
          valid: (allowPartialLineup || meetsMin) && meetsMax,
        };
      });

    return {
      errors,
      counts,
      tierRows,
      totalActive: currentStarters.length,
      totalRequired: activeRosterRequired,
      totalValid:
        currentStarters.length <= activeRosterRequired &&
        (allowPartialLineup || currentStarters.length >= activeRosterRequired),
    };
  }, [
    rosterState,
    activeRosterRequired,
    maxPositionLimits,
    starterRequirements,
    allowPartialLineup,
  ]);

  const openReadOnlyRuleView = useCallback((ruleType) => {
    setRuleViewerType(ruleType);
    setShowRuleViewer(true);
  }, []);

  // when tierRows change we auto-expand all of them so headers are visible
  useEffect(() => {
    setExpandedPositions(
      new Set(lineupRuleSnapshot.tierRows.map((t) => t.position))
    );
  }, [lineupRuleSnapshot.tierRows]);

  const currentStarterValidationErrors = useMemo(
    () => lineupRuleSnapshot.errors,
    [lineupRuleSnapshot.errors]
  );

  const lineupValidationErrors = useMemo(
    () => [...new Set(currentStarterValidationErrors)],
    [currentStarterValidationErrors]
  );

  const canEditLineup =
    !!currentUserId && (!viewedOwnerId || viewedOwnerId === currentUserId);

  const hasUnsavedLineupChanges = useMemo(() => {
    if (!rosterState.length) return false;
    return rosterState.some((player) => {
      const baselineStatus =
        baselineLineupStatus[String(player.player_id)] || 'BENCH';
      return (player.status || 'BENCH') !== baselineStatus;
    });
  }, [rosterState, baselineLineupStatus]);

  const activeLineupPlayers = useMemo(
    () =>
      sortRosterByHierarchy(
        rosterState.filter((player) => player.status === 'STARTER')
      ),
    [rosterState]
  );

  const benchLineupPlayers = useMemo(
    () =>
      sortRosterByHierarchy(
        rosterState.filter((player) => player.status !== 'STARTER')
      ),
    [rosterState]
  );

  const benchNormal = useMemo(
    () => benchLineupPlayers.filter((p) => !p.is_taxi),
    [benchLineupPlayers]
  );
  const benchTaxi = useMemo(
    () => benchLineupPlayers.filter((p) => p.is_taxi),
    [benchLineupPlayers]
  );

  const movePlayerToStatus = useCallback(
    (playerId, targetStatus) => {
      if (!canEditLineup) return;
      if (viewMode === 'actual') {
        setRosterState((prev) => {
          const target = prev.find(
            (player) => Number(player.player_id) === Number(playerId)
          );
          if (!target) return prev;
          if (target.is_locked) {
            setToast({
              message: `${target.name} is locked for Week ${selectedWeek} (game already started).`,
              type: 'error',
            });
            return prev;
          }
          return prev.map((player) =>
            Number(player.player_id) === Number(playerId)
              ? { ...player, status: targetStatus }
              : player
          );
        });
      } else {
        // recommended view
        setRecState((prev) => {
          const target = prev.find(
            (player) =>
              Number(player.id || player.player_id) === Number(playerId)
          );
          if (!target) return prev;
          return prev.map((player) =>
            Number(player.id || player.player_id) === Number(playerId)
              ? { ...player, status: targetStatus }
              : player
          );
        });
      }
    },
    [canEditLineup, selectedWeek, viewMode]
  );

  const handleDragStart = useCallback(
    (player) => {
      if (!canEditLineup || player.is_locked) return;
      setDraggingPlayerId(player.player_id || player.id);
    },
    [canEditLineup]
  );

  const handleDropToStatus = useCallback(
    (targetStatus) => {
      if (!draggingPlayerId) return;
      movePlayerToStatus(draggingPlayerId, targetStatus);
      setDraggingPlayerId(null);
    },
    [draggingPlayerId, movePlayerToStatus]
  );

  const submitRoster = async () => {
    if (!canEditLineup) return;
    if (lineupValidationErrors.length > 0) {
      setShowLineupValidationModal(true);
      setToast({
        message: 'Fix lineup validation issues before submitting roster.',
        type: 'error',
      });
      return;
    }

    setSubmittingRoster(true);
    try {
      // filter out taxi players; backend ignores them and will otherwise
      // treat them as missing starters which triggers validation errors.
      const starters = rosterState.filter(
        (player) => player.status === 'STARTER'
      );
      const taxiStarters = starters.filter((p) => p.is_taxi);
      if (taxiStarters.length > 0) {
        setToast({
          message:
            'Taxi players are not counted as starters and have been removed.',
          type: 'error',
        });
      }
      const starterIds = starters
        .filter((p) => !p.is_taxi)
        .map((player) => Number(player.player_id));

      console.log('Submitting roster payload', {
        week: selectedWeek,
        starter_player_ids: starterIds,
      });

      await apiClient.post('/team/lineup', {
        week: selectedWeek,
        starter_player_ids: starterIds,
      });

      await apiClient.post('/team/submit-lineup', {
        week: selectedWeek,
      });

      setToast({
        message: `Week ${selectedWeek} roster submitted successfully.`,
        type: 'success',
      });
      fetchTeam();
    } catch (err) {
      console.error('submitRoster error', err);
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail) && detail.length > 0) {
        setToast({ message: detail.join(', '), type: 'error' });
      } else {
        setToast({
          message: detail || 'Failed to submit roster.',
          type: 'error',
        });
      }
    } finally {
      setSubmittingRoster(false);
    }
  };

  useEffect(() => {
    if (lineupValidationErrors.length > 0) {
      setShowLineupValidationModal(true);
    } else {
      setShowLineupValidationModal(false);
    }
  }, [lineupValidationErrors.length, selectedWeek]);

  const handleSubmitTradeProposal = async () => {
    console.log('handleSubmitTradeProposal called', {
      canProposeTrade,
      proposalToUserId,
      offeredPlayerId,
      requestedPlayerId,
      offeredDollars,
      requestedDollars,
    });
    if (!canProposeTrade) {
      setToast({
        message: 'Trades can only be proposed from your own roster page.',
        type: 'error',
      });
      return;
    }

    if (!proposalToUserId || !offeredPlayerId || !requestedPlayerId) {
      setToast({ message: 'Select manager and both players.', type: 'error' });
      return;
    }

    try {
      await apiClient.post('/trades/propose', {
        to_user_id: Number(proposalToUserId),
        offered_player_id: Number(offeredPlayerId),
        requested_player_id: Number(requestedPlayerId),
        offered_dollars: Number(offeredDollars) || 0,
        requested_dollars: Number(requestedDollars) || 0,
        note: proposalNote,
      });

      setToast({ message: 'Trade proposal submitted.', type: 'success' });
      setShowProposeTrade(false);
      setProposalToUserId('');
      setOfferedPlayerId('');
      setRequestedPlayerId('');
      setProposalNote('');
      setOfferedDollars('');
      setRequestedDollars('');
      fetchTeam();
    } catch (err) {
      setToast({
        message:
          err.response?.data?.detail || 'Failed to submit trade proposal.',
        type: 'error',
      });
    }
  };

  const openPlayerPerformance = async (player) => {
    setSelectedPlayer(player);
    setShowPlayerPerformance(true);
    setPlayerPerformanceLoading(true);

    try {
      const currentSeason = new Date().getFullYear();
      const res = await apiClient.get(
        `/players/${player.id}/season-details?season=${currentSeason}`
      );
      setPlayerPerformance(res.data);
    } catch {
      setPlayerPerformance(null);
      setToast({
        message: 'Unable to load player season details right now.',
        type: 'error',
      });
    } finally {
      setPlayerPerformanceLoading(false);
    }
  };

  // taxi controls
  const handleDemoteToTaxi = async (playerId) => {
    try {
      await apiClient.post('/team/taxi/demote', { player_id: playerId });
      fetchTeam();
      setToast({ message: 'Player moved to taxi squad.', type: 'success' });
    } catch {
      // error is intentionally ignored; UI shows a generic message
      setToast({ message: 'Unable to move player to taxi.', type: 'error' });
    }
  };

  const handlePromoteFromTaxi = async (playerId) => {
    try {
      await apiClient.post('/team/taxi/promote', { player_id: playerId });
      fetchTeam();
      setToast({ message: 'Player promoted from taxi.', type: 'success' });
    } catch {
      // error intentionally ignored
      setToast({
        message: 'Unable to promote player from taxi.',
        type: 'error',
      });
    }
  };

  // --- 2.1 RENDER LOGIC (The View) ---

  if (loading)
    return (
      <div
        className={`${pageShell} animate-pulse text-slate-600 dark:text-slate-400`}
      >
        Loading Roster...
      </div>
    );
  if (!teamData)
    return (
      <div className={`${pageShell} text-red-500`}>Error loading team.</div>
    );

  const controlButtonClass =
    'px-4 py-2 rounded font-bold text-sm whitespace-nowrap';

  const lineupIsValid = lineupValidationErrors.length === 0;

  // --- LOCKER ROOM/ROSTER/WAIVER UI (from Dashboard.jsx) ---
  if (!summary)
    return (
      <div
        className={`${pageShell} text-center animate-pulse text-slate-500 dark:text-slate-400 font-black`}
      >
        Loading your locker room...
      </div>
    );

  return (
    <div className={`${pageShell} text-slate-900 dark:text-white min-h-screen`}>
      {/* Commissioner Modals */}
      <ScoringRulesModal
        open={showScoring}
        onClose={() => setShowScoring(false)}
      />
      <WaiverWireRulesModal
        open={showWaivers}
        onClose={() => setShowWaivers(false)}
      />
      <TradeRulesModal open={showTrades} onClose={() => setShowTrades(false)} />

      {showRuleViewer && (
        <div className={modalOverlay}>
          <div className={`${modalSurface} max-w-2xl p-6`}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className={modalTitle}>
                {ruleViewerType === 'scoring' && 'Scoring Rules'}
                {ruleViewerType === 'waiver' && 'Waiver Wire Rules'}
                {ruleViewerType === 'trade' && 'Trade Rules'}
                {ruleViewerType === 'keeper' && 'Keeper Rules'}
              </h3>
              <button
                onClick={() => setShowRuleViewer(false)}
                className={modalCloseButton}
              >
                <FiX />
              </button>
            </div>

            <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-4 text-sm text-slate-200">
              <p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400">
                Read-only view
              </p>

              {ruleViewerType === 'scoring' && (
                <div className="space-y-2">
                  {scoringRules.length === 0 ? (
                    <p className="text-slate-400">
                      No scoring rules configured.
                    </p>
                  ) : (
                    scoringRules.slice(0, 10).map((rule, index) => (
                      <div
                        key={`${rule.category}-${rule.event_name}-${index}`}
                        className="rounded border border-slate-800 bg-slate-950/40 px-3 py-2"
                      >
                        <div className="font-bold text-slate-100">
                          {rule.event_name}
                        </div>
                        <div className="text-xs text-slate-400">
                          {rule.category} • {rule.point_value} pts
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {ruleViewerType === 'waiver' && (
                <p>
                  Waiver deadline:{' '}
                  <span className="font-bold">
                    {waiverDeadlineSetting
                      ? new Date(waiverDeadlineSetting).toLocaleString()
                      : 'Not configured'}
                  </span>
                </p>
              )}

              {ruleViewerType === 'trade' && (
                <p>
                  Trade deadline:{' '}
                  <span className="font-bold">
                    {tradeDeadlineSetting
                      ? new Date(tradeDeadlineSetting).toLocaleString()
                      : 'Not configured'}
                  </span>
                </p>
              )}

              {ruleViewerType === 'keeper' && (
                <p>
                  Keeper settings are commissioner-managed. You can review your
                  keeper selections on the Manage Keepers page.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* HEADER SECTION */}
      <div className={`${pageHeader} mb-6`}>
        <h1 className={pageTitle}>Your Locker Room</h1>
        <p className={pageSubtitle}>
          Manage lineups, waivers, trades, and keeper decisions.
        </p>

        <div className="mt-6 flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() =>
                userInfo.is_commissioner
                  ? setShowScoring(true)
                  : openReadOnlyRuleView('scoring')
              }
              className={`${controlButtonClass} ${buttonSecondary}`}
            >
              Scoring Rules
            </button>
            <button
              onClick={() =>
                userInfo.is_commissioner
                  ? setShowWaivers(true)
                  : openReadOnlyRuleView('waiver')
              }
              className={`${controlButtonClass} ${buttonSecondary}`}
            >
              Waiver Wire Rules
            </button>
            <button
              onClick={() =>
                userInfo.is_commissioner
                  ? setShowTrades(true)
                  : openReadOnlyRuleView('trade')
              }
              className={`${controlButtonClass} ${buttonSecondary}`}
            >
              Trade Rules
            </button>
            {userInfo.is_commissioner ? (
              <Link
                to="/commissioner/keeper-rules"
                className={`${controlButtonClass} ${buttonSecondary}`}
              >
                Keeper Rules
              </Link>
            ) : (
              <button
                onClick={() => openReadOnlyRuleView('keeper')}
                className={`${controlButtonClass} ${buttonSecondary}`}
              >
                Keeper Rules
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/waivers"
              className={`${controlButtonClass} ${buttonPrimary} inline-flex items-center justify-center gap-2`}
            >
              <FiPlus className="text-base" /> Waiver Wire
            </Link>
            <Link
              to="/keepers"
              className={`${controlButtonClass} ${buttonPrimary} inline-flex items-center justify-center gap-2`}
            >
              <FiRepeat className="text-base" /> Manage Keepers
            </Link>

            {canProposeTrade && (
              <button
                onClick={() => setShowProposeTrade(true)}
                className={`${controlButtonClass} ${buttonPrimary}`}
              >
                <div className="flex items-center justify-center gap-2 whitespace-nowrap">
                  <FiSend className="text-base" /> Propose Trade
                </div>
              </button>
            )}

            <div
              className={`${controlButtonClass} inline-flex items-center gap-2 border border-slate-700 bg-slate-900 text-slate-200`}
            >
              <FiRepeat className="text-base text-blue-400" />
              <span className="uppercase">Pending Trades</span>
              <span className="font-black">{summary.pending_trades}</span>
            </div>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3 text-slate-400">
          <p className="flex items-center gap-2">
            Current Standing:{' '}
            <span className="bg-purple-600 text-white px-3 py-1 rounded-lg font-black italic">
              #{summary.standing} Place
            </span>
          </p>
          {/* deadlines indicators */}
          {waiverRemaining && userInfo.draftStatus !== 'ACTIVE' && (
            <p className="inline-flex items-center gap-2 rounded-lg border border-blue-500/40 bg-blue-900/20 px-3 py-2 text-xs font-black uppercase tracking-widest text-blue-300">
              Waiver Deadline: {waiverRemaining}
            </p>
          )}
          {tradeRemaining && userInfo.draftStatus !== 'ACTIVE' && (
            <p className="inline-flex items-center gap-2 rounded-lg border border-yellow-500/40 bg-yellow-900/20 px-3 py-2 text-xs font-black uppercase tracking-widest text-yellow-300">
              Trade Deadline: {tradeRemaining}
            </p>
          )}
          {userInfo.draftStatus === 'ACTIVE' && (
            <p className="inline-flex items-center gap-2 rounded-lg border border-orange-500/40 bg-orange-900/20 px-3 py-2 text-xs font-black uppercase tracking-widest text-orange-300">
              Draft Active • Waiver Wire Locked
            </p>
          )}
        </div>
      </div>

      {showProposeTrade && canProposeTrade && (
        <div className={modalOverlay}>
          <div className={`${modalSurface} max-w-2xl p-6`}>
            <div className="mb-5 flex items-center justify-between">
              <h3 className={modalTitle}>Propose Trade</h3>
              <button
                onClick={() => setShowProposeTrade(false)}
                className={modalCloseButton}
              >
                <FiX />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label
                  htmlFor="trade-with"
                  className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400"
                >
                  Trade With
                </label>
                <select
                  id="trade-with"
                  value={proposalToUserId}
                  onChange={(e) => setProposalToUserId(e.target.value)}
                  className={inputBase}
                >
                  <option value="">Select manager</option>
                  {leagueOwners
                    .filter((owner) => owner.id !== currentUserId)
                    .map((owner) => (
                      <option key={owner.id} value={owner.id}>
                        {owner.team_name || owner.username}
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="you-offer"
                  className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400"
                >
                  You Offer
                </label>
                <select
                  id="you-offer"
                  value={offeredPlayerId}
                  onChange={(e) => setOfferedPlayerId(e.target.value)}
                  className={inputBase}
                >
                  <option value="">Select your player</option>
                  {myTradeRoster.map((player) => (
                    <option key={player.id} value={player.id}>
                      {player.name} ({player.position})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="you-request"
                  className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400"
                >
                  You Request
                </label>
                <select
                  id="you-request"
                  value={requestedPlayerId}
                  onChange={(e) => setRequestedPlayerId(e.target.value)}
                  className={inputBase}
                  disabled={!proposalToUserId}
                >
                  <option value="">Select requested player</option>
                  {targetRoster.map((player) => (
                    <option key={player.id} value={player.id}>
                      {player.name} ({player.position})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex gap-4">
                <div className="flex-1">
                  <label
                    htmlFor="offered-dollars"
                    className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400"
                  >
                    Offer $ (future draft)
                  </label>
                  <input
                    id="offered-dollars"
                    type="number"
                    min="0"
                    step="1"
                    value={offeredDollars}
                    onChange={(e) => setOfferedDollars(e.target.value)}
                    className={inputBase}
                    placeholder="0"
                  />
                </div>
                <div className="flex-1">
                  <label
                    htmlFor="requested-dollars"
                    className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400"
                  >
                    Request $ (future draft)
                  </label>
                  <input
                    id="requested-dollars"
                    type="number"
                    min="0"
                    step="1"
                    value={requestedDollars}
                    onChange={(e) => setRequestedDollars(e.target.value)}
                    className={inputBase}
                    placeholder="0"
                    disabled={!proposalToUserId}
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-400">
                  Note (Optional)
                </label>
                <textarea
                  rows={3}
                  value={proposalNote}
                  onChange={(e) => setProposalNote(e.target.value)}
                  className={inputBase}
                  placeholder="Add context for commissioner review"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setShowProposeTrade(false)}
                className={buttonSecondary}
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitTradeProposal}
                className={buttonPrimary}
              >
                Submit Proposal
              </button>
            </div>
          </div>
        </div>
      )}

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

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
                  <div className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-3">
                    <div className="text-[10px] uppercase text-slate-500">
                      Games
                    </div>
                    <div className="text-xl font-black text-slate-900 dark:text-white">
                      {playerPerformance.games_played}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-3">
                    <div className="text-[10px] uppercase text-slate-500">
                      Total Pts
                    </div>
                    <div className="text-xl font-black text-blue-400">
                      {Number(
                        playerPerformance.total_fantasy_points || 0
                      ).toFixed(2)}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-3">
                    <div className="text-[10px] uppercase text-slate-500">
                      Avg / Game
                    </div>
                    <div className="text-xl font-black text-slate-900 dark:text-white">
                      {Number(
                        playerPerformance.average_fantasy_points || 0
                      ).toFixed(2)}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-3">
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
                  <div className="bg-slate-100 dark:bg-slate-950 px-4 py-2 text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-2">
                    <FiBarChart2 /> Weekly Breakdown
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    {(playerPerformance.weekly || []).length === 0 ? (
                      <div className="p-6 text-center text-slate-500">
                        No weekly performance data yet for this season.
                      </div>
                    ) : (
                      <table className="w-full text-left text-sm text-slate-700 dark:text-slate-300">
                        <thead className="bg-slate-100 dark:bg-slate-900 text-xs uppercase text-slate-500">
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

      {showLineupValidationModal && lineupValidationErrors.length > 0 && (
        <div className={modalOverlay}>
          <div className="w-full max-w-2xl rounded-2xl border border-red-800/60 bg-white dark:bg-slate-950 p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-lg font-black tracking-tight text-red-500 dark:text-red-300">
                <FiAlertTriangle /> Lineup Validation
              </h3>
              <button
                onClick={() => setShowLineupValidationModal(false)}
                className={modalCloseButton}
              >
                <FiX />
              </button>
            </div>

            <div className="rounded-lg border border-red-900/40 bg-red-900/10 p-4">
              <p className="mb-2 text-xs font-bold uppercase tracking-wider text-red-200">
                Week {selectedWeek} requirements are not satisfied:
              </p>
              <ul className="space-y-1 text-sm text-red-100">
                {lineupValidationErrors.map((error) => (
                  <li key={error} className="flex items-center gap-2">
                    <span>•</span>
                    <span>{error}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      <div
        className={`${cardSurface} mb-8 border-2 ${
          lineupIsValid
            ? 'border-green-500/40 bg-green-900/5'
            : 'border-red-500/40 bg-red-900/5'
        }`}
      >
        <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="text-xl font-black uppercase tracking-wider text-slate-900 dark:text-white">
              Lineup Builder (Drag & Drop)
            </h3>
            <p className="text-xs uppercase tracking-wide text-slate-400">
              Move players between Active and Bench. Started players are locked
              for this week.
            </p>
            <p className="mt-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <span className="text-green-300">Green = valid tier</span> •{' '}
              <span className="text-red-300">Red = invalid tier</span>
            </p>
            <p
              className={`mt-2 inline-flex items-center rounded-md px-2 py-1 text-[11px] font-black uppercase tracking-wider ${
                lineupIsValid
                  ? 'bg-green-900/30 text-green-200'
                  : 'bg-red-900/30 text-red-200'
              }`}
            >
              {lineupIsValid ? 'Lineup Valid' : 'Lineup Invalid'}
            </p>
          </div>

          <div className="flex flex-col items-end gap-2">
            <div className="flex flex-wrap items-center justify-end gap-2">
              <button
                onClick={() => setViewMode('recommended')}
                className={`px-4 py-2 ${
                  viewMode === 'recommended' ? buttonPrimary : buttonSecondary
                }`}
              >
                Recommended
              </button>
              <button
                onClick={() => setViewMode('actual')}
                className={`px-4 py-2 ${
                  viewMode === 'actual' ? buttonPrimary : buttonSecondary
                }`}
              >
                Actual
              </button>

              <label className="ml-2 text-xs font-bold uppercase tracking-wider text-slate-400">
                Week
              </label>
              <select
                value={selectedWeek}
                onChange={(event) =>
                  setSelectedWeek(Number(event.target.value))
                }
                className={`${inputBase} w-auto text-sm font-bold`}
              >
                {weekOptions.map((week) => (
                  <option key={week} value={week}>
                    Week {week}
                  </option>
                ))}
              </select>
              <select
                value={startSitSort}
                onChange={(event) => setStartSitSort(event.target.value)}
                className={`${inputBase} w-auto text-sm font-bold`}
              >
                <option value="projected">Sort: Projected</option>
                <option value="position">
                  Sort: Hierarchy (QB/RB/WR/TE/DEF)
                </option>
              </select>

              {viewMode === 'actual' && (
                <button
                  type="button"
                  onClick={submitRoster}
                  disabled={
                    submittingRoster ||
                    !canEditLineup ||
                    lineupValidationErrors.length > 0
                  }
                  className={`rounded-lg px-4 py-2 text-xs font-black uppercase tracking-wider ${
                    submittingRoster ||
                    !canEditLineup ||
                    lineupValidationErrors.length > 0
                      ? `${buttonSecondary} cursor-not-allowed opacity-50`
                      : buttonPrimary
                  }`}
                >
                  {submittingRoster ? 'Submitting...' : 'Submit Roster'}
                </button>
              )}
            </div>

            {(hasUnsavedLineupChanges || lineupSubmittedForWeek) && (
              <div className="flex flex-wrap items-center justify-end gap-2">
                {hasUnsavedLineupChanges && (
                  <span className="rounded-md border border-yellow-700/60 bg-yellow-900/20 px-3 py-2 text-[11px] font-black uppercase tracking-wider text-yellow-300">
                    Unsaved Changes
                  </span>
                )}
                {lineupSubmittedForWeek && (
                  <span className="rounded-md border border-green-700/60 bg-green-900/20 px-3 py-2 text-[11px] font-black uppercase tracking-wider text-green-300">
                    Week {selectedWeek} Submitted
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {lineupValidationErrors.length > 0 && (
          <button
            type="button"
            onClick={() => setShowLineupValidationModal(true)}
            className="mb-4 inline-flex items-center gap-2 rounded-lg border border-red-800/50 bg-red-900/20 px-3 py-2 text-xs font-black uppercase tracking-wider text-red-200"
          >
            <FiAlertTriangle />
            Lineup has validation issues ({lineupValidationErrors.length})
          </button>
        )}

        {viewMode === 'recommended' && (
          <>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-green-400/40 bg-green-100/60 p-4 dark:border-green-900/60 dark:bg-green-900/10">
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="text-sm font-black uppercase tracking-widest text-green-700 dark:text-green-300">
                    Recommended Starts
                  </h4>
                  <span className="rounded bg-green-200 px-2 py-1 text-xs font-bold text-green-800 dark:bg-green-900/30 dark:text-green-200">
                    {sortedStartRecommendations.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {sortedStartRecommendations.map((player) => (
                    <div
                      key={`start-${player.id}`}
                      className="flex items-center justify-between rounded-lg border border-slate-300 bg-white/80 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/70"
                    >
                      <div>
                        <div className="text-sm font-bold text-slate-900 dark:text-white">
                          {player.name}
                        </div>
                        <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
                          {getPlayerSlotLabel(player)} • {player.nfl_team}
                        </div>
                      </div>
                      <div className="text-sm font-mono font-bold text-green-300">
                        {Number(player.projected_for_week || 0).toFixed(1)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-red-400/40 bg-red-100/60 p-4 dark:border-red-900/60 dark:bg-red-900/10">
                <div className="mb-3 flex items-center justify-between">
                  <h4 className="text-sm font-black uppercase tracking-widest text-red-700 dark:text-red-300">
                    Recommended Sits
                  </h4>
                  <span className="rounded bg-red-200 px-2 py-1 text-xs font-bold text-red-800 dark:bg-red-900/30 dark:text-red-200">
                    {sortedSitRecommendations.length + byePlayers.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {byePlayers.map((player) => (
                    <div
                      key={`bye-${player.id}`}
                      className="flex items-center justify-between rounded-lg border border-orange-400/50 bg-orange-100/60 px-3 py-2 dark:border-orange-800/60 dark:bg-orange-900/20"
                    >
                      <div>
                        <div className="text-sm font-bold text-slate-900 dark:text-white">
                          {player.name}
                        </div>
                        <div className="text-[11px] uppercase tracking-wide text-orange-700 dark:text-orange-300">
                          BYE WEEK • {normalizePosition(player.position)} •{' '}
                          {player.nfl_team}
                        </div>
                      </div>
                      <div className="text-xs font-black uppercase tracking-wider text-orange-300">
                        Sit
                      </div>
                    </div>
                  ))}
                  {sortedSitRecommendations.map((player) => (
                    <div
                      key={`sit-${player.id}`}
                      className="flex items-center justify-between rounded-lg border border-slate-300 bg-white/80 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/70"
                    >
                      <div>
                        <div className="text-sm font-bold text-slate-900 dark:text-white">
                          {player.name}
                        </div>
                        <div className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
                          {getPlayerSlotLabel(player)} • {player.nfl_team}
                        </div>
                      </div>
                      <div className="text-sm font-mono font-bold text-red-300">
                        {Number(player.projected_for_week || 0).toFixed(1)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
        {viewMode === 'actual' && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div
              className="rounded-xl border border-green-400/40 bg-green-100/60 p-4 dark:border-green-900/60 dark:bg-green-900/10"
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => handleDropToStatus('STARTER')}
            >
              <div className="mb-3 flex items-center justify-between">
                <h4 className="text-sm font-black uppercase tracking-widest text-green-700 dark:text-green-300">
                  Active
                </h4>
                <span className="rounded bg-green-200 px-2 py-1 text-xs font-bold text-green-800 dark:bg-green-900/30 dark:text-green-200">
                  {activeLineupPlayers.length}
                </span>
              </div>
              <div className="space-y-2">
                {lineupRuleSnapshot.tierRows.map((tier) => {
                  const pos = tier.position;
                  const isExpanded = expandedPositions.has(pos);
                  const playersForPos = activeLineupPlayers.filter(
                    (p) => normalizePosition(p.position) === pos
                  );
                  const containerBorder = tier.valid
                    ? 'border-green-400'
                    : 'border-red-400';
                  const badgeColor = tier.valid
                    ? 'bg-green-900/20 text-green-300'
                    : 'bg-red-900/20 text-red-300';
                  return (
                    <div
                      className="rounded-md border border-slate-300 bg-white/50 p-2 dark:border-slate-700 dark:bg-slate-900/30"
                      key={pos}
                    >
                      <div
                        className="flex items-center justify-between cursor-pointer"
                        onClick={() => togglePosition(pos)}
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold uppercase text-slate-900 dark:text-white">
                            {pos}
                          </span>
                          <span className="text-xs">
                            {isExpanded ? '▼' : '▶'}
                          </span>
                          <span
                            className={`rounded-md px-2 py-1 text-xs font-bold ${badgeColor}`}
                          >
                            {tier.actual} ({tier.minimum}-{tier.maximum})
                          </span>
                        </div>
                      </div>
                      {isExpanded && (
                        <div
                          className={`mt-2 space-y-2 border p-2 bg-white/70 dark:bg-slate-950/40 ${containerBorder}`}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={() => handleDropToStatus('STARTER')}
                        >
                          {playersForPos.map((player) => (
                            <button
                              key={`active-${player.player_id}`}
                              type="button"
                              draggable={canEditLineup && !player.is_locked}
                              onDragStart={() => handleDragStart(player)}
                              onClick={() => openPlayerPerformance(player)}
                              className={`w-full rounded-lg border px-3 py-2 text-left ${
                                player.is_locked
                                  ? 'cursor-not-allowed border-orange-800/60 bg-orange-900/20'
                                  : 'border-slate-300 bg-white hover:border-blue-500/50 dark:border-slate-800 dark:bg-slate-950/70'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <div>
                                  <div className="text-sm font-bold text-slate-900 dark:text-white">
                                    {player.name}
                                  </div>
                                  <div className="text-[11px] uppercase tracking-wide text-slate-600 dark:text-slate-400">
                                    {normalizePosition(player.position)} •{' '}
                                    {player.nfl_team}
                                  </div>
                                </div>
                                <div className="text-sm font-mono font-bold text-green-300">
                                  {Number(toProjectedPoints(player)).toFixed(1)}
                                </div>
                              </div>
                              {player.is_locked && (
                                <div className="mt-1 text-[10px] font-black uppercase tracking-wider text-orange-300">
                                  Locked (game started)
                                </div>
                              )}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <div
              className="rounded-xl border border-slate-300 bg-slate-100/60 p-4 dark:border-slate-700 dark:bg-slate-900/30"
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => handleDropToStatus('BENCH')}
            >
              <div className="mb-3 flex items-center justify-between">
                <h4 className="text-sm font-black uppercase tracking-widest text-slate-700 dark:text-slate-300">
                  Bench
                </h4>
                <span className="rounded bg-slate-200 px-2 py-1 text-xs font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  {benchLineupPlayers.length}
                </span>
              </div>
              <div className="space-y-2">
                {benchNormal.map((player) => (
                  <div
                    key={`bench-${player.player_id}`}
                    role="button"
                    tabIndex={0}
                    draggable={canEditLineup && !player.is_locked}
                    onDragStart={() => handleDragStart(player)}
                    onClick={() => openPlayerPerformance(player)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ')
                        openPlayerPerformance(player);
                    }}
                    className={`w-full rounded-lg border px-3 py-2 text-left focus:outline-none focus:ring-2 focus:ring-blue-400 ${
                      player.is_locked
                        ? 'cursor-not-allowed border-orange-800/60 bg-orange-900/20'
                        : 'cursor-pointer border-slate-300 bg-white hover:border-blue-500/50 dark:border-slate-800 dark:bg-slate-950/70'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-sm font-bold text-slate-900 dark:text-white">
                          {player.name}
                        </div>
                        <div className="text-[11px] uppercase tracking-wide text-slate-600 dark:text-slate-400">
                          {normalizePosition(player.position)} •{' '}
                          {player.nfl_team}
                        </div>
                      </div>
                      <div className="text-sm font-mono font-bold text-slate-700 dark:text-slate-300">
                        {Number(toProjectedPoints(player)).toFixed(1)}
                      </div>
                    </div>
                    {canEditLineup && !player.is_taxi && (
                      <div className="mt-2 flex justify-end">
                        <span
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDemoteToTaxi(player.player_id);
                          }}
                          className="inline-block cursor-pointer text-xs bg-yellow-600 hover:bg-yellow-500 text-black px-2 py-1 rounded"
                        >
                          Taxi
                        </span>
                      </div>
                    )}
                    {player.is_locked && (
                      <div className="mt-1 text-[10px] font-black uppercase tracking-wider text-orange-300">
                        Locked (game started)
                      </div>
                    )}
                  </div>
                ))}
                {benchTaxi.length > 0 && (
                  <>
                    <div className="mt-4 font-bold uppercase text-yellow-700 dark:text-yellow-300">
                      Taxi Squad
                    </div>
                    {benchTaxi.map((player) => (
                      <div
                        key={`taxi-${player.player_id}`}
                        role="button"
                        tabIndex={0}
                        draggable={canEditLineup && !player.is_locked}
                        onDragStart={() => handleDragStart(player)}
                        onClick={() => openPlayerPerformance(player)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ')
                            openPlayerPerformance(player);
                        }}
                        className={`w-full rounded-lg border px-3 py-2 text-left focus:outline-none focus:ring-2 focus:ring-yellow-400 ${
                          player.is_locked
                            ? 'cursor-not-allowed border-orange-800/60 bg-orange-900/20'
                            : 'cursor-pointer border-yellow-500/50 bg-yellow-100/60 hover:border-yellow-500/50 dark:border-yellow-800 dark:bg-yellow-900/10'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-sm font-bold text-slate-900 dark:text-white">
                              {player.name}
                            </div>
                            <div className="text-[11px] uppercase tracking-wide text-slate-600 dark:text-slate-400">
                              {normalizePosition(player.position)} •{' '}
                              {player.nfl_team}
                            </div>
                          </div>
                          <div className="text-sm font-mono font-bold text-slate-700 dark:text-slate-300">
                            {Number(toProjectedPoints(player)).toFixed(1)}
                          </div>
                        </div>
                        {canEditLineup && player.is_taxi && (
                          <div className="mt-2 flex justify-end">
                            <span
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePromoteFromTaxi(player.player_id);
                              }}
                              className="inline-block cursor-pointer text-xs bg-green-600 hover:bg-green-500 text-white px-2 py-1 rounded"
                            >
                              Promote
                            </span>
                          </div>
                        )}
                        {player.is_locked && (
                          <div className="mt-1 text-[10px] font-black uppercase tracking-wider text-orange-300">
                            Locked (game started)
                          </div>
                        )}
                        <div className="mt-1 text-[10px] font-black uppercase tracking-wider text-yellow-300">
                          Taxi Squad
                        </div>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-3xl border border-slate-300 bg-white/80 p-8 dark:border-slate-800 dark:bg-slate-900/70">
        <h3 className="mb-6 flex items-center gap-2 text-xl font-black uppercase italic tracking-tighter text-slate-900 dark:text-slate-200">
          <FiBell className="text-blue-400" /> Sit-Rep
        </h3>
        <ul className="space-y-6">
          <li className="relative pl-6">
            <div className="absolute left-0 top-1 w-1 h-10 bg-purple-500 rounded-full"></div>
            <p className="mb-1 text-xs font-bold uppercase tracking-widest text-slate-500 dark:text-slate-400">
              Waiver Deadline
            </p>
            <p className="text-lg font-black text-slate-900 dark:text-white">
              {waiverRemaining || 'No deadline set'}
            </p>
          </li>
          <li className="relative pl-6 opacity-60">
            <div className="absolute left-0 top-1 w-1 h-10 bg-blue-500 rounded-full"></div>
            <p className="mb-1 text-xs font-bold uppercase tracking-widest text-slate-500 dark:text-slate-400">
              Draft Status
            </p>
            <p className="text-lg font-black tracking-tight uppercase text-slate-900 dark:text-white">
              {String(userInfo.draftStatus || 'PRE_DRAFT').replaceAll('_', ' ')}
            </p>
          </li>
        </ul>
      </div>
    </div>
  );
}
