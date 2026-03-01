import { useEffect, useState } from 'react';
import apiClient from '@api/client';
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
  const [budgetRows, setBudgetRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !leagueId) return;
    setLoading(true);
    Promise.all([
      apiClient.get(`/leagues/${leagueId}/settings`),
      apiClient.get(`/leagues/owners?league_id=${leagueId}`),
    ])
      .then(([settingsRes, ownersRes]) => {
        const year = settingsRes.data?.draft_year || new Date().getFullYear();
        setDraftYear(year);

        const owners = ownersRes.data || [];
        return apiClient
          .get(`/leagues/${leagueId}/budgets?year=${year}`)
          .then((budgetsRes) => {
            const rows = budgetsRes.data || [];
            if (rows.length === 0) {
              const seeded = owners.map((owner) => ({
                owner_id: owner.id,
                username: owner.username,
                team_name: owner.team_name,
                total_budget: 200,
              }));
              setBudgetRows(seeded);
            } else {
              setBudgetRows(rows);
            }
          })
          .catch(() => {
            // budgets call failed (table missing or error); seed owners
            const seeded = owners.map((owner) => ({
              owner_id: owner.id,
              username: owner.username,
              team_name: owner.team_name,
              total_budget: 200,
            }));
            setBudgetRows(seeded);
          });
      })
      .catch(() => {
        setBudgetRows([]);
      })
      .finally(() => setLoading(false));
  }, [open, leagueId]);

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
          {loading && (
            <div className="text-sm text-slate-500 dark:text-slate-400">
              Loading budgets...
            </div>
          )}
          {!loading &&
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
        <div className="mt-6 flex justify-end gap-3">
          <button className={buttonSecondary} onClick={onClose}>
            Close
          </button>
          <button
            className={buttonPrimary}
            disabled={saving}
            onClick={async () => {
              if (!leagueId) return;
              setSaving(true);
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
                onClose();
              } catch {
                alert('Failed to save budgets.');
              } finally {
                setSaving(false);
              }
            }}
          >
            Save Budgets
          </button>
        </div>
      </div>
    </div>
  );
}
