import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';
import { Link } from 'react-router-dom';
import {
  buttonPrimary,
  buttonSecondary,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '@utils/uiStandards';

/* ignore-breakpoints */

export default function Keepers() {
  const [keeperData, setKeeperData] = useState(null);
  const [roster, setRoster] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [locking, setLocking] = useState(false);
  // base budget is derived from keeper data and roster rather than state
  // (keeps eslint happy and avoids cascading renders)
  // const [baseBudget, setBaseBudget] = useState(0); // now derived via memo

  const userId = localStorage.getItem('user_id');

  // fetch keeper info and roster once per user
  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await apiClient.get('/keepers');
        setKeeperData(res.data);
        if (res.data && Array.isArray(res.data.selections)) {
          setSelected(new Set(res.data.selections.map((s) => s.player_id)));
        }
      } catch (err) {
        console.error('failed to load keeper data', err);
      }
      if (userId) {
        try {
          // backend rejects week 0, fall back to 1 if necessary
          const weekParam = 1;
          const rres = await apiClient.get(`/team/${userId}?week=${weekParam}`);
          setRoster(Array.isArray(rres.data?.roster) ? rres.data.roster : []);
        } catch (e) {
          console.error('failed to load roster', e);
          setRoster([]);
        }
      }
      setLoading(false);
    }
    load();
  }, [userId]);

  // compute base budget from the latest data
  const computedBaseBudget = React.useMemo(() => {
    if (!keeperData || roster.length === 0) return 0;
    let initialCost = 0;
    keeperData.selections.forEach((s) => {
      const p = roster.find((r) => r.player_id === s.player_id);
      if (p) initialCost += Number(p.draft_price || 0);
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
      await apiClient.post('/keepers', payload);
      // refresh
      const res = await apiClient.get('/keepers');
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
      const res = await apiClient.get('/keepers');
      setKeeperData(res.data);
    } catch (e) {
      console.error('failed to lock keepers', e);
    }
    setLocking(false);
  };

  if (loading) {
    return (
      <div className={`${pageShell} text-slate-600 dark:text-slate-400`}>
        Loading keepers...
      </div>
    );
  }

  const maxAllowed = keeperData?.max_allowed || 0;
  const selectedCount = selected.size;
  const estimatedBudget =
    computedBaseBudget -
    Array.from(selected).reduce((sum, pid) => {
      const p = roster.find((r) => r.player_id === pid);
      return sum + Number(p?.draft_price || 0);
    }, 0);

  return (
    <div className={`${pageShell} min-h-screen text-slate-900 dark:text-white`}>
      <div
        className={`${pageHeader} flex flex-col gap-3 md:flex-row md:items-start md:justify-between`}
      >
        <div>
          <h1 className={pageTitle}>Manage Keepers</h1>
          <p className={pageSubtitle}>
            Review keeper slots, submit, and lock selections.
          </p>
        </div>
        <div className="text-sm text-slate-700 dark:text-slate-300">
          Estimated Budget: ${estimatedBudget}
          <br />
          Draft Budget: ${keeperData?.effective_budget ?? 0}
        </div>
      </div>

      <div className="text-yellow-300">
        {selectedCount} of {maxAllowed} chosen
      </div>

      {/* slot grid */}
      <div className="grid grid-cols-6 gap-4">
        {Array.from({ length: maxAllowed }).map((_, idx) => {
          const pid = Array.from(selected)[idx];
          const player = roster.find((r) => r.player_id === pid);
          return (
            <div
              key={idx}
              onClick={() => player && togglePlayer(player.player_id)}
              className={`cursor-pointer h-24 w-full border rounded-lg flex flex-col items-center justify-center p-1 ${
                keeperData?.recommended?.some(
                  (r) => r.player_id === player?.player_id
                )
                  ? 'border-yellow-400'
                  : 'border-slate-600'
              }`}
            >
              {player ? (
                <>
                  <span className="font-semibold">Selected Keeper</span>
                  <span className="text-xs text-slate-600 dark:text-slate-300">
                    ${player.draft_price || 0}
                    {player.projected_value != null && (
                      <> / ${player.projected_value}</>
                    )}
                  </span>
                  {keeperData?.recommended?.some(
                    (r) => r.player_id === player.player_id
                  ) && <span className="text-yellow-300 text-xs">★</span>}
                </>
              ) : (
                <span className="text-slate-500 dark:text-slate-400">
                  Empty
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* roster selector */}
      <div className="space-y-2">
        {roster.map((p) => {
          const isRec = keeperData?.recommended?.some(
            (r) => r.player_id === p.player_id
          );
          return (
            <label key={p.player_id} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={selected.has(p.player_id)}
                onChange={() => togglePlayer(p.player_id)}
                disabled={
                  keeperData?.ineligible?.includes(p.player_id) ||
                  (!selected.has(p.player_id) && selectedCount >= maxAllowed)
                }
              />
              <span>{p.name}</span>
              <span>(draft: ${p.draft_price || 0})</span>
              {keeperData?.ineligible?.includes(p.player_id) && (
                <span
                  className="text-red-400 text-xs ml-1"
                  title="Reached max keeper years"
                >
                  🚫
                </span>
              )}
              {p.projected_value != null && (
                <span className="text-slate-500 dark:text-slate-400 text-xs">
                  &nbsp;| proj: ${p.projected_value}
                </span>
              )}
              {isRec && <span className="ml-1 text-yellow-300 text-xs">★</span>}
            </label>
          );
        })}
      </div>
      {keeperData?.recommended && keeperData.recommended.length > 0 && (
        <div className="mt-4 text-yellow-300">
          <strong>Recommended surplus</strong>
          <ul className="list-disc list-inside">
            {keeperData.recommended.map((r) => (
              <li key={r.player_id}>
                ID {r.player_id}: surplus ${r.surplus.toFixed(1)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex gap-4">
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

      <Link
        to="/team"
        className={`${buttonSecondary} inline-flex w-fit gap-2 px-3 py-1.5 text-xs no-underline`}
      >
        ← Back to My Team
      </Link>
    </div>
  );
}
