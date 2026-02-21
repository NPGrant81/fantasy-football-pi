import { useEffect, useState } from 'react';
import apiClient from '@api/client';

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
          });
      })
      .catch(() => {
        setBudgetRows([]);
      })
      .finally(() => setLoading(false));
  }, [open, leagueId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 w-full max-w-2xl shadow-2xl">
        <h2 className="text-xl font-black text-white uppercase tracking-tight">
          Set Draft Budgets
        </h2>
        <p className="text-slate-400 text-sm mt-2">
          Assign budgets for the {draftYear} season. These budgets apply to the
          current league year.
        </p>
        <div className="mt-4">
          <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
            Draft Year
          </label>
          <input
            type="number"
            className="w-full p-2 rounded bg-slate-950 border border-slate-700 text-white"
            value={draftYear}
            onChange={(e) =>
              setDraftYear(parseInt(e.target.value) || new Date().getFullYear())
            }
          />
        </div>
        <div className="mt-4 space-y-2 max-h-72 overflow-y-auto">
          {loading && (
            <div className="text-slate-500 text-sm">Loading budgets...</div>
          )}
          {!loading &&
            budgetRows.map((row) => (
              <div
                key={row.owner_id}
                className="flex items-center justify-between gap-3 bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2"
              >
                <div>
                  <div className="text-sm font-bold text-white">
                    {row.team_name || row.username}
                  </div>
                  <div className="text-xs text-slate-400">
                    Owner: {row.username}
                  </div>
                </div>
                <input
                  type="number"
                  className="w-28 p-2 rounded bg-slate-900 border border-slate-700 text-white text-right"
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
          <button
            className="px-4 py-2 rounded border border-slate-700 text-slate-300"
            onClick={onClose}
          >
            Close
          </button>
          <button
            className="px-4 py-2 rounded bg-yellow-500 text-black font-bold"
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
