import { useEffect, useState } from 'react';
import apiClient from '@api/client';
import { normalizeApiError } from '@api/fetching';
import { EmptyState, LoadingState } from '@components/common/AsyncState';
import {
  buttonPrimary,
  buttonSecondary,
  inputBase,
  modalCloseButton,
  modalDescription,
  modalOverlay,
  modalSurface,
  modalTitle,
} from '@utils/uiStandards';

export default function DraftBudgetsModal({ open, onClose, leagueId }) {
  const [draftYear, setDraftYear] = useState(new Date().getFullYear());
  const [owners, setOwners] = useState([]);
  const [budgetRows, setBudgetRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [budgetLoading, setBudgetLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Load settings + owners whenever the modal opens
  useEffect(() => {
    if (!open || !leagueId) {
      setOwners([]);
      setBudgetRows([]);
      return;
    }
    let isMounted = true;
    setLoading(true);
    setSaveError('');
    setSaveSuccess(false);
    Promise.all([
      apiClient.get(`/leagues/${leagueId}/settings`),
      apiClient.get(`/leagues/owners?league_id=${leagueId}`),
    ])
      .then(([settingsRes, ownersRes]) => {
        if (!isMounted) return;
        const year = settingsRes.data?.draft_year || new Date().getFullYear();
        setDraftYear(year);
        setOwners(Array.isArray(ownersRes.data) ? ownersRes.data : []);
      })
      .catch(() => {
        if (isMounted) setOwners([]);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [open, leagueId]);

  // Reload budget rows whenever the draft year or owner list changes
  useEffect(() => {
    if (!open || !leagueId || owners.length === 0) {
      setBudgetRows([]);
      return;
    }
    let isMounted = true;
    setBudgetLoading(true);
    setSaveError('');
    const seed = owners.map((o) => ({
      owner_id: o.id,
      username: o.username,
      team_name: o.team_name,
      total_budget: 200,
    }));
    apiClient
      .get(`/leagues/${leagueId}/budgets?year=${draftYear}`)
      .then((res) => {
        if (!isMounted) return;
        const rows = res.data || [];
        setBudgetRows(rows.length > 0 ? rows : seed);
      })
      .catch(() => {
        if (isMounted) setBudgetRows(seed);
      })
      .finally(() => {
        if (isMounted) setBudgetLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [open, leagueId, draftYear, owners]);

  if (!open) return null;

  return (
    <div className={modalOverlay}>
      <div className={`${modalSurface} sm:max-w-2xl p-6`}>
        <button className={modalCloseButton} onClick={onClose}>
          ✕
        </button>
        <h2 className={modalTitle}>Set Draft Budgets</h2>
        <p className={`${modalDescription} mt-2`}>
          Assign budgets for the {draftYear} season. These budgets apply to the
          current league year.
        </p>
        <div className="mt-4">
          <label className="mb-2 block text-xs font-bold uppercase text-slate-600 dark:text-slate-400">
            Draft Year
          </label>
          <input
            type="number"
            className={inputBase}
            value={draftYear}
            onChange={(e) =>
              setDraftYear(parseInt(e.target.value) || new Date().getFullYear())
            }
          />
        </div>
        <div className="mt-4 space-y-2 max-h-72 overflow-y-auto">
          {(loading || budgetLoading) && (
            <LoadingState message="Loading budgets..." className="text-sm text-slate-500 dark:text-slate-400" />
          )}
          {!loading && !budgetLoading && budgetRows.length === 0 ? (
            <EmptyState message="No budget rows available." className="text-sm" />
          ) : null}
          {!loading && !budgetLoading &&
            budgetRows.map((row) => (
              <div
                key={row.owner_id}
                className="flex items-center justify-between gap-3 rounded-lg border border-slate-300 bg-white/60 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/60"
              >
                <div>
                  <div className="text-sm font-bold text-slate-900 dark:text-white">
                    {row.team_name || row.username}
                  </div>
                  <div className="text-xs text-slate-600 dark:text-slate-400">
                    Owner: {row.username}
                  </div>
                </div>
                <input
                  type="number"
                  className={`${inputBase} w-28 text-right`}
                  value={row.total_budget ?? 200}
                  onChange={(e) => {
                    const next = budgetRows.map((item) =>
                      item.owner_id === row.owner_id
                        ? {
                            ...item,
                            total_budget: parseInt(e.target.value) || 0,
                          }
                        : item
                    );
                    setBudgetRows(next);
                  }}
                />
              </div>
            ))}
        </div>
        {saveSuccess && (
          <p className="mt-3 text-sm font-semibold text-green-600 dark:text-green-400">
            Budgets saved — ledger entries created.
          </p>
        )}
        {saveError && (
          <p className="mt-3 text-sm text-red-500 dark:text-red-400">{saveError}</p>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <button className={buttonSecondary} onClick={onClose}>
            Close
          </button>
          <button
            className={buttonPrimary}
            disabled={saving || loading || budgetLoading}
            onClick={async () => {
              if (!leagueId) return;
              setSaving(true);
              setSaveError('');
              setSaveSuccess(false);
              try {
                await apiClient.post(`/leagues/${leagueId}/draft-year`, {
                  year: draftYear,
                });
                await apiClient.post(`/leagues/${leagueId}/budgets`, {
                  year: draftYear,
                  budgets: budgetRows.map((row) => ({
                    owner_id: row.owner_id,
                    total_budget: row.total_budget ?? 200,
                  })),
                });
                setSaveSuccess(true);
                setTimeout(onClose, 1500);
              } catch (err) {
                setSaveError(normalizeApiError(err, 'Failed to save budgets.'));
              } finally {
                setSaving(false);
              }
            }}
          >
            {saving ? 'Saving…' : 'Save Budgets'}
          </button>
        </div>
      </div>
    </div>
  );
}
