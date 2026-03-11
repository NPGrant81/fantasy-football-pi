/* ignore-breakpoints: modal layout and responsiveness are handled by shared uiStandards modal classes; no additional breakpoint-specific behaviour is required */
import { useEffect, useState } from 'react';
import { FiSettings } from 'react-icons/fi';
import apiClient from '@api/client';
import { normalizeApiError } from '@api/fetching';
import {
  StandardTable,
  StandardTableContainer,
  StandardTableHead,
  StandardTableRow,
  StandardTableStateRow,
} from '@components/table/TablePrimitives';
import {
  modalCloseButton,
  modalDescription,
  modalOverlay,
  modalSurface,
  modalTitle,
  tableCell,
  textMuted,
} from '@utils/uiStandards';
import { CALC_TYPE_LABEL } from '@utils/scoringRules';

export default function ScoringRulesModal({ open, onClose }) {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) {
      return;
    }

    let cancelled = false;

    async function loadRules() {
      setLoading(true);
      setError('');
      try {
        const res = await apiClient.get('/scoring/rules?include_inactive=false');
        if (!cancelled) {
          setRules(Array.isArray(res.data) ? res.data : []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(normalizeApiError(err, 'Failed to load scoring rules.'));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadRules();

    return () => {
      cancelled = true;
    };
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

        {!loading && !error && rules.length > 0 && (
          <StandardTableContainer className="mt-4 overflow-x-auto">
            <StandardTable className="border-collapse">
              <StandardTableHead
                headers={[
                  { key: 'category', label: 'Category', className: 'py-2 pr-3' },
                  { key: 'event', label: 'Event', className: 'py-2 pr-3' },
                  { key: 'type', label: 'Type', className: 'py-2 pr-3' },
                  { key: 'points', label: 'Points', className: 'py-2 pr-3' },
                  { key: 'positions', label: 'Positions', className: 'py-2 pr-3' },
                  { key: 'season', label: 'Season', className: 'py-2' },
                ]}
              />
              <tbody>
                {loading && <StandardTableStateRow colSpan={6}>Loading rules…</StandardTableStateRow>}
                {error && <StandardTableStateRow colSpan={6}>{error}</StandardTableStateRow>}
                {!loading && !error && rules.length === 0 && (
                  <StandardTableStateRow colSpan={6}>
                    No scoring rules have been configured for this league yet.
                  </StandardTableStateRow>
                )}
                {rules.map((rule) => (
                  <StandardTableRow
                    key={rule.id}
                    className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  >
                    <td className={tableCell}>{rule.category}</td>
                    <td className={tableCell}>{rule.event_name}</td>
                    <td className={tableCell}>{CALC_TYPE_LABEL[rule.calculation_type] || rule.calculation_type}</td>
                    <td className={tableCell}>{rule.point_value}</td>
                    <td className={tableCell}>{(rule.applicable_positions || []).join(', ') || 'ALL'}</td>
                    <td className={tableCell}>{rule.season_year || 'All seasons'}</td>
                  </StandardTableRow>
                ))}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        )}
        {loading && <p className={`${textMuted} mt-3`}>Loading rules…</p>}
        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
        {!loading && !error && rules.length === 0 && (
          <p className={`${textMuted} mt-3`}>No scoring rules have been configured for this league yet.</p>
        )}
      </div>
    </div>
  );
}
