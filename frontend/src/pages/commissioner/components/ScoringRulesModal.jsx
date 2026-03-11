/* ignore-breakpoints: modal layout and responsiveness are handled by shared uiStandards modal classes; no additional breakpoint-specific behaviour is required */
import { useEffect, useState } from 'react';
import { FiSettings } from 'react-icons/fi';
import apiClient from '@api/client';
import { normalizeApiError } from '@api/fetching';
import {
  modalCloseButton,
  modalDescription,
  modalOverlay,
  modalSurface,
  modalTitle,
  tableCell,
  textMuted,
} from '@utils/uiStandards';

const CALC_TYPE_LABEL = {
  flat_bonus: 'Flat Bonus',
  per_unit: 'Per Unit',
  decimal: 'Decimal',
  ppr: 'PPR',
  half_ppr: 'Half-PPR',
  tiered: 'Tiered Range',
};

export default function ScoringRulesModal({ open, onClose }) {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError('');
    apiClient
      .get('/scoring/rules?include_inactive=false')
      .then((res) => setRules(Array.isArray(res.data) ? res.data : []))
      .catch((err) => setError(normalizeApiError(err, 'Failed to load scoring rules.')))
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  return (
    <div className={modalOverlay}>
      <div className={`${modalSurface} max-w-3xl w-full`}>
        <button onClick={onClose} className={modalCloseButton}>
          ✕
        </button>
        <h2 className={modalTitle}>
          <FiSettings className="inline mr-1" /> League Scoring Rules
        </h2>
        <p className={modalDescription}>
          Current active scoring rules configured by your commissioner.
        </p>

        {loading && (
          <p className={`${textMuted} mt-3`}>Loading rules…</p>
        )}
        {error && (
          <p className="mt-3 text-sm text-red-400">{error}</p>
        )}
        {!loading && !error && rules.length === 0 && (
          <p className={`${textMuted} mt-3`}>No scoring rules have been configured for this league yet.</p>
        )}
        {!loading && !error && rules.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
                  <th className="py-2 pr-3">Category</th>
                  <th className="py-2 pr-3">Event</th>
                  <th className="py-2 pr-3">Type</th>
                  <th className="py-2 pr-3">Points</th>
                  <th className="py-2 pr-3">Positions</th>
                  <th className="py-2">Season</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr
                    key={rule.id}
                    className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  >
                    <td className={tableCell}>{rule.category}</td>
                    <td className={tableCell}>{rule.event_name}</td>
                    <td className={tableCell}>{CALC_TYPE_LABEL[rule.calculation_type] || rule.calculation_type}</td>
                    <td className={tableCell}>{rule.point_value}</td>
                    <td className={tableCell}>{(rule.applicable_positions || []).join(', ') || 'ALL'}</td>
                    <td className={tableCell}>{rule.season_year || 'All seasons'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
