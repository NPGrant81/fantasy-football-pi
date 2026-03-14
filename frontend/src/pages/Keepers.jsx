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

export default function Keepers() {
  const [keeperData, setKeeperData] = useState(null);
  const [roster, setRoster] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [locking, setLocking] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [ownerId, setOwnerId] = useState(
    localStorage.getItem('user_id') || null
  );
  // base budget is derived from keeper data and roster rather than state
  // (keeps eslint happy and avoids cascading renders)
  // const [baseBudget, setBaseBudget] = useState(0); // now derived via memo

  // fetch authenticated owner identity once so roster loading does not depend
  // on localStorage being present after session restore.
  useEffect(() => {
    async function loadOwner() {
      try {
        const res = await apiClient.get('/auth/me');
        const nextOwnerId = res?.data?.user_id;
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

  // fetch keeper info and roster once per authenticated user
  useEffect(() => {
    async function load() {
      if (!ownerId) return;

      setLoading(true);
      setLoadError('');
      try {
        const res = await apiClient.get('/keepers/');
        setKeeperData(res.data);
        if (res.data && Array.isArray(res.data.selections)) {
          setSelected(new Set(res.data.selections.map((s) => s.player_id)));
        }
      } catch (err) {
        console.error('failed to load keeper data', err);
        setLoadError('Unable to load keeper data right now.');
      }
      try {
        // backend rejects week 0, fall back to 1 if necessary
        const weekParam = 1;
        const rres = await apiClient.get(`/team/${ownerId}?week=${weekParam}`);
        const nextRoster = Array.isArray(rres.data?.players)
          ? rres.data.players
          : Array.isArray(rres.data?.roster)
            ? rres.data.roster
            : [];
        setRoster(nextRoster);
      } catch (e) {
        console.error('failed to load roster', e);
        setRoster([]);
        setLoadError((current) => current || 'Unable to load roster right now.');
      }
      setLoading(false);
    }

    void load();
  }, [ownerId]);

  // compute base budget from the latest data
  const computedBaseBudget = React.useMemo(() => {
    if (!keeperData || roster.length === 0) return 0;
    let initialCost = 0;
    keeperData.selections.forEach((s) => {
      const p = roster.find((r) => r.player_id === s.player_id);
      if (p) initialCost += Number(p.acquisition_cost || 0);
    });
    return (keeperData.estimated_budget || 0) + initialCost;
  }, [keeperData, roster]);

  const togglePlayer = (playerId) => {
    const newSel = new Set(selected);
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
      setKeeperData(res.data);
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
      setKeeperData(res.data);
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
  const estimatedBudget =
    computedBaseBudget -
    Array.from(selected).reduce((sum, pid) => {
      const p = roster.find((r) => r.player_id === pid);
      return sum + Number(p?.acquisition_cost || 0);
    }, 0);

  return (
    <PageTemplate
      title="Manage Keepers"
      subtitle="Review keeper slots, submit, and lock selections."
      metadata={`Estimated Budget: $${estimatedBudget} | Draft Budget: $${keeperData.effective_budget ?? 0}`}
      actions={
        <Link
          to="/team"
          className={`${buttonSecondary} inline-flex gap-2 px-3 py-1.5 text-xs no-underline`}
        >
          ← Back to My Team
        </Link>
      }
    >
      <div className={cardSurface}>
        <p className="text-sm font-bold text-slate-700 dark:text-slate-300">
          {selectedCount} of {maxAllowed} chosen
        </p>
      </div>

      <div className={cardSurface}>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
          {Array.from({ length: maxAllowed }).map((_, idx) => {
            const pid = Array.from(selected)[idx];
            const player = roster.find((r) => r.player_id === pid);
            return (
              <div
                key={idx}
                onClick={() => player && togglePlayer(player.player_id)}
                className={`h-24 w-full cursor-pointer rounded-lg border p-1 flex flex-col items-center justify-center ${
                  keeperData.recommended?.some(
                    (r) => r.player_id === player?.player_id
                  )
                    ? 'border-yellow-500'
                    : 'border-slate-300 dark:border-slate-700'
                }`}
              >
                {player ? (
                  <>
                    <span className="font-semibold text-slate-900 dark:text-white">Selected Keeper</span>
                    <span className="text-xs text-slate-600 dark:text-slate-300">
                      ${player.acquisition_cost || 0}
                      {player.projected_value != null && (
                        <> / ${player.projected_value}</>
                      )}
                    </span>
                    {keeperData.recommended?.some(
                      (r) => r.player_id === player.player_id
                    ) && <span className="text-yellow-500 text-xs">★</span>}
                  </>
                ) : (
                  <span className="text-slate-500 dark:text-slate-400">Empty</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className={cardSurface}>
        <div className="space-y-2">
          {roster.map((p) => {
            const isRec = keeperData.recommended?.some(
              (r) => r.player_id === p.player_id
            );
            return (
              <label key={p.player_id} className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={selected.has(p.player_id)}
                  onChange={() => togglePlayer(p.player_id)}
                  disabled={
                    keeperData.ineligible?.includes(p.player_id) ||
                    (!selected.has(p.player_id) && selectedCount >= maxAllowed)
                  }
                />
                <span>{p.name}</span>
                <span>(draft: ${p.acquisition_cost || 0})</span>
                {keeperData.ineligible?.includes(p.player_id) && (
                  <span
                    className="ml-1 text-xs text-red-500"
                    title="Reached max keeper years"
                  >
                    🚫
                  </span>
                )}
                {p.projected_value != null && (
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    &nbsp;| proj: ${p.projected_value}
                  </span>
                )}
                {isRec && <span className="ml-1 text-xs text-yellow-500">★</span>}
              </label>
            );
          })}
        </div>
      </div>

      {keeperData.recommended && keeperData.recommended.length > 0 && (
        <div className={cardSurface}>
          <strong className="text-slate-900 dark:text-white">Recommended surplus</strong>
          <ul className="list-disc list-inside text-slate-700 dark:text-slate-300">
            {keeperData.recommended.map((r) => (
              <li key={r.player_id}>
                ID {r.player_id}: surplus ${r.surplus.toFixed(1)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className={`${cardSurface} flex gap-4`}>
        <button
          onClick={handleSubmit}
          disabled={saving}
          className={`${buttonPrimary} px-4 py-2`}
        >
          {saving ? 'Saving...' : 'Submit List'}
        </button>
        <button
          onClick={handleLock}
          disabled={locking}
          className={`${buttonSecondary} px-4 py-2`}
        >
          {locking ? 'Locking...' : 'Lock In Keepers'}
        </button>
      </div>
    </PageTemplate>
  );
}
