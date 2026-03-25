import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';
import { Link } from 'react-router-dom';
import { ErrorState, LoadingState } from '@components/common/AsyncState';
import PageTemplate from '@components/layout/PageTemplate';
import {
  cardSurface,
  buttonPrimary,
  buttonSecondary,
  pageShell,
} from '@utils/uiStandards';

/* ignore-breakpoints */

const getPlayerCost = (player) => {
  const amount = Number(player?.acquisition_cost ?? player?.draft_price ?? 0);
  return Number.isFinite(amount) ? amount : 0;
};

const normalizeKeeperPlayer = (player, options = {}) => {
  const playerId = player?.player_id ?? player?.id;
  const yearsKeptCount = Number(player?.years_kept_count ?? 0);
  const cost = getPlayerCost(player);

  return {
    ...player,
    player_id: playerId,
    name: player?.name ?? 'Unknown Player',
    position: player?.position ?? '',
    nfl_team: player?.nfl_team ?? null,
    acquisition_cost: cost,
    draft_price: cost,
    is_selected: Boolean(options.isSelected ?? player?.is_selected),
    is_eligible: Boolean(options.isEligible ?? player?.is_eligible ?? true),
    reason_ineligible: options.reasonIneligible ?? player?.reason_ineligible ?? null,
    years_kept_count: Number.isFinite(yearsKeptCount) ? yearsKeptCount : 0,
  };
};

const normalizeKeeperResponse = (data, ownerIdentity) => {
  const selections = Array.isArray(data?.selections) ? data.selections : [];
  const selectedIds = new Set(selections.map((selection) => selection.player_id));
  const ineligibleIds = new Set(Array.isArray(data?.ineligible) ? data.ineligible : []);
  const availablePlayers = Array.isArray(data?.available_players)
    ? data.available_players.map((player) => {
        const playerId = player?.player_id ?? player?.id;
        const defaultReason = ineligibleIds.has(playerId)
          ? 'Reached max keeper years'
          : null;

        return normalizeKeeperPlayer(player, {
          isSelected: selectedIds.has(playerId),
          isEligible: player?.is_eligible ?? !ineligibleIds.has(playerId),
          reasonIneligible: player?.reason_ineligible ?? defaultReason,
        });
      })
    : [];

  return {
    ...data,
    owner_name:
      data?.owner_name || ownerIdentity?.team_name || ownerIdentity?.username || 'My Team',
    effective_budget: Number(data?.effective_budget ?? 0),
    estimated_budget: Number(data?.estimated_budget ?? data?.effective_budget ?? 0),
    max_allowed: Number(data?.max_allowed ?? 3),
    selections,
    recommended: Array.isArray(data?.recommended) ? data.recommended : [],
    available_players: availablePlayers,
  };
};

export default function Keepers() {
  const [keeperData, setKeeperData] = useState(null);
  const [rosterFallback, setRosterFallback] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [ownerIdentity, setOwnerIdentity] = useState(null);
  const [ownerId, setOwnerId] = useState(
    localStorage.getItem('user_id') || null
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [locking, setLocking] = useState(false);
  const [loadError, setLoadError] = useState('');

  // Resolve owner from session when localStorage is empty/stale.
  useEffect(() => {
    async function loadOwner() {
      try {
        const res = await apiClient.get('/auth/me');
        const nextOwnerId = res?.data?.user_id;
        setOwnerIdentity(res?.data || null);
        if (nextOwnerId) {
          setOwnerId(String(nextOwnerId));
          localStorage.setItem('user_id', String(nextOwnerId));
        }
      } catch (err) {
        console.error('failed to load authenticated owner', err);
        setLoadError((current) => current || 'Unable to load keeper data right now.');
      }
    }

    void loadOwner();
  }, []);

  // fetch keeper info once owner identity is available
  useEffect(() => {
    async function load() {
      if (!ownerIdentity && !ownerId) {
        return;
      }

      setLoading(true);
      setLoadError('');
      try {
        const res = await apiClient.get('/keepers/');
        const normalizedKeeperData = normalizeKeeperResponse(
          res.data,
          ownerIdentity
        );
        setKeeperData(normalizedKeeperData);
        if (normalizedKeeperData.selections.length > 0) {
          setSelected(
            new Set(normalizedKeeperData.selections.map((selection) => selection.player_id))
          );
        } else {
          setSelected(new Set());
        }

        const hasAvailablePlayers =
          normalizedKeeperData.available_players.length > 0;
        if (!hasAvailablePlayers && ownerId) {
          try {
            const rres = await apiClient.get(`/team/${ownerId}?week=1`);
            const fallbackPlayers = Array.isArray(rres.data?.players)
              ? rres.data.players
              : Array.isArray(rres.data?.roster)
                ? rres.data.roster
                : [];
            setRosterFallback(
              fallbackPlayers.map((player) =>
                normalizeKeeperPlayer(player, {
                  isSelected: selected.has(player?.player_id ?? player?.id),
                })
              )
            );
          } catch (fallbackErr) {
            console.error('failed to load roster fallback', fallbackErr);
            setRosterFallback([]);
          }
        } else {
          setRosterFallback([]);
        }
      } catch (err) {
        console.error('failed to load keeper data', err);
        setLoadError('Unable to load keeper data right now.');
      }
      setLoading(false);
    }

    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerId, ownerIdentity]);

  const togglePlayer = (playerId, isEligible) => {
    const newSel = new Set(selected);
    // Allow deselecting existing picks even if they became ineligible.
    if (!isEligible && !newSel.has(playerId)) return;

    if (newSel.has(playerId)) {
      newSel.delete(playerId);
    } else {
      newSel.add(playerId);
    }
    setSelected(newSel);
  };

  const handleSubmit = async () => {
    if (!keeperData) return;
    setSaving(true);
    const payload = {
      players: Array.from(selected).map((pid) => ({
        player_id: pid,
        keep_cost: 0,
        years_kept_count: 0,
        status: 'pending',
        approved_by_commish: false,
      })),
    };
    try {
      await apiClient.post('/keepers/', payload);
      // refresh
      const res = await apiClient.get('/keepers/');
      const normalizedKeeperData = normalizeKeeperResponse(res.data, ownerIdentity);
      setKeeperData(normalizedKeeperData);
      setSelected(
        new Set(normalizedKeeperData.selections.map((selection) => selection.player_id))
      );
    } catch (e) {
      console.error('failed to submit keepers', e);
    }
    setSaving(false);
  };

  const handleLock = async () => {
    setLocking(true);
    try {
      await apiClient.post('/keepers/lock');
      const res = await apiClient.get('/keepers/');
      const normalizedKeeperData = normalizeKeeperResponse(res.data, ownerIdentity);
      setKeeperData(normalizedKeeperData);
      setSelected(
        new Set(normalizedKeeperData.selections.map((selection) => selection.player_id))
      );
    } catch (e) {
      console.error('failed to lock keepers', e);
    }
    setLocking(false);
  };

  if (loading) {
    return (
      <div className={pageShell}>
        <LoadingState message="Loading keepers..." />
      </div>
    );
  }

  if (!keeperData) {
    return (
      <div className={pageShell}>
        <ErrorState
          message={loadError || 'No keeper data available.'}
          className="mt-6"
        />
      </div>
    );
  }

  const maxAllowed = keeperData.max_allowed || 0;
  const selectedCount = selected.size;
  const displayedPlayers =
    keeperData.available_players && keeperData.available_players.length > 0
      ? keeperData.available_players
      : rosterFallback;

  const computedBaseBudget = keeperData.selections.reduce(
    (sum, selection) => {
      const player = displayedPlayers.find(
        (candidate) => candidate.player_id === selection.player_id
      );
      return sum + getPlayerCost(player);
    },
    Number(keeperData.estimated_budget ?? keeperData.effective_budget ?? 0)
  );

  const estimatedBudget =
    computedBaseBudget -
    Array.from(selected).reduce((sum, pid) => {
      const player = displayedPlayers.find((candidate) => candidate.player_id === pid);
      return sum + getPlayerCost(player);
    }, 0);

  return (
    <PageTemplate
      title={`Manage Keepers - ${keeperData.owner_name}`}
      subtitle="Review your roster, select eligible players to keep, and lock in your keepers."
      metadata={`Effective Budget: $${keeperData.effective_budget ?? 0} | Estimated Budget: $${estimatedBudget} | ${selectedCount} of ${maxAllowed} chosen`}
      actions={
        <Link
          to="/team"
          className={`${buttonSecondary} inline-flex gap-2 px-3 py-1.5 text-xs no-underline`}
        >
          ← Back to My Team
        </Link>
      }
    >
      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className={cardSurface}>
          <div className="text-sm font-bold text-slate-700 dark:text-slate-300">
            Selected Keepers
          </div>
          <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
            {selectedCount}/{maxAllowed}
          </div>
        </div>
        <div className={cardSurface}>
          <div className="text-sm font-bold text-slate-700 dark:text-slate-300">
            Effective Draft Budget
          </div>
          <div className="text-3xl font-bold text-green-600 dark:text-green-400">
            ${keeperData.effective_budget ?? 0}
          </div>
        </div>
        <div className={cardSurface}>
          <div className="text-sm font-bold text-slate-700 dark:text-slate-300">
            Estimated Budget
          </div>
          <div className="text-3xl font-bold text-slate-600 dark:text-slate-400">
            ${estimatedBudget}
          </div>
        </div>
      </div>

      {/* Keeper selection boxes (visual representation of slots) */}
      <div className={cardSurface}>
        <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-3">
          Your Keeper Slots
        </h3>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
          {Array.from({ length: maxAllowed }).map((_, idx) => {
            const selectedArray = Array.from(selected);
            const playerId = selectedArray[idx];
            const player = displayedPlayers.find(
              (p) => p.player_id === playerId
            );
            return (
              <div
                key={idx}
                onClick={() => player && togglePlayer(player.player_id, player.is_eligible)}
                className={`h-24 w-full cursor-pointer rounded-lg border-2 p-2 flex flex-col items-center justify-center text-center transition ${
                  player
                    ? 'border-blue-500 bg-blue-50 dark:bg-slate-800'
                    : 'border-dashed border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-900'
                }`}
              >
                {player ? (
                  <>
                    <span className="font-semibold text-xs text-slate-900 dark:text-white line-clamp-2">
                      {player.name}
                    </span>
                    <span className="text-xs text-slate-600 dark:text-slate-300 font-medium">
                      {player.position}
                    </span>
                    <span className="text-xs text-blue-600 dark:text-blue-400">
                      ${getPlayerCost(player)}
                    </span>
                    {keeperData.recommended?.some(
                      (recommendation) => recommendation.player_id === player.player_id
                    ) && <span className="text-yellow-500 text-xs">★</span>}
                  </>
                ) : (
                  <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                    Empty Slot
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Available players list */}
      <div className={cardSurface}>
        <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-3">
          Your Roster - Available to Keep
        </h3>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {displayedPlayers.length > 0 ? (
            displayedPlayers.map((p) => {
              const isSelected = selected.has(p.player_id);
              return (
                <label
                  key={p.player_id}
                  className={`flex items-center gap-3 p-2 rounded cursor-pointer transition ${
                    p.is_eligible
                      ? 'hover:bg-slate-100 dark:hover:bg-slate-800'
                      : 'opacity-60 cursor-not-allowed'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => togglePlayer(p.player_id, p.is_eligible)}
                    disabled={!p.is_eligible || (isSelected === false && selectedCount >= maxAllowed)}
                    className="cursor-pointer"
                  />
                  <span className={`flex-1 ${!p.is_eligible ? 'text-slate-500' : 'text-slate-700 dark:text-slate-300'}`}>
                    {p.name}
                  </span>
                  <span className={`text-xs px-2 py-1 rounded ${isSelected ? 'bg-blue-200 dark:bg-blue-900 text-blue-900 dark:text-blue-100' : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300'}`}>
                    {p.position}
                  </span>
                  <span className="text-xs text-slate-600 dark:text-slate-400 font-medium w-16 text-right">
                    ${getPlayerCost(p)}
                  </span>
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    draft: ${getPlayerCost(p)}
                  </span>
                  {!p.is_eligible && (
                    <span
                      className="text-xs text-red-600 dark:text-red-400 font-medium"
                      title={p.reason_ineligible || 'Reached max keeper years'}
                    >
                      ❌ {p.reason_ineligible?.split(';')[0]}
                    </span>
                  )}
                  {p.years_kept_count > 0 && p.is_eligible && (
                    <span className="text-xs text-yellow-600 dark:text-yellow-400 font-medium">
                      {p.years_kept_count} yr{p.years_kept_count > 1 ? 's' : ''}
                    </span>
                  )}
                  {keeperData.recommended?.some(
                    (recommendation) => recommendation.player_id === p.player_id
                  ) && <span className="ml-1 text-xs text-yellow-500">★</span>}
                </label>
              );
            })
          ) : (
            <div className="text-center text-slate-500 dark:text-slate-400 py-4">
              No players available to keep in your roster
            </div>
          )}
        </div>
      </div>

      {/* Recommended keepers section */}
      {keeperData.recommended && keeperData.recommended.length > 0 && (
        <div className={cardSurface}>
          <strong className="text-slate-900 dark:text-white text-sm">💡 Recommended Keepers (Surplus Value)</strong>
          <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 text-xs mt-2 space-y-1">
            {keeperData.recommended.slice(0, 5).map((r) => {
              const player = displayedPlayers.find((p) => p.player_id === r.player_id);
              return (
                <li key={r.player_id}>
                  {player?.name ?? `ID ${r.player_id}`} ({player?.position ?? 'N/A'}) - ${r.surplus.toFixed(1)} surplus
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Action buttons */}
      <div className={`${cardSurface} flex gap-4 flex-wrap`}>
        <button
          onClick={handleSubmit}
          disabled={saving}
          className={`${buttonPrimary} px-4 py-2 text-sm`}
        >
          {saving ? 'Saving...' : 'Save Selections'}
        </button>
        <button
          onClick={handleLock}
          disabled={locking}
          className={`${buttonSecondary} px-4 py-2 text-sm`}
        >
          {locking ? 'Locking...' : 'Lock In Keepers'}
        </button>
      </div>
    </PageTemplate>
  );
}
