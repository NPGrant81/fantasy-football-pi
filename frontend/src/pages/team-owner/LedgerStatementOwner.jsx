import { useEffect, useState } from 'react';
import apiClient from '@api/client';
import {
  cardSurface,
  inputBase,
  pageShell,
  tableHead,
  tableSurface,
} from '@utils/uiStandards';

const CURRENCY_OPTIONS = [
  { value: '', label: 'All currencies' },
  { value: 'DRAFT_DOLLARS', label: 'Draft Dollars' },
  { value: 'FAAB', label: 'FAAB' },
];

export default function LedgerStatementOwner() {
  const leagueId = localStorage.getItem('fantasyLeagueId');
  const [currencyType, setCurrencyType] = useState('');
  const [seasonYear, setSeasonYear] = useState('');
  const [statementLoading, setStatementLoading] = useState(false);
  const [statement, setStatement] = useState(null);

  useEffect(() => {
    if (!leagueId) return;

    let isMounted = true;
    const loadStatement = async () => {
      setStatementLoading(true);
      try {
        const params = new URLSearchParams();
        params.append('limit', '200');
        if (currencyType) params.append('currency_type', currencyType);
        if (seasonYear) params.append('season_year', seasonYear);

        const res = await apiClient.get(
          `/leagues/${leagueId}/ledger/statement?${params.toString()}`
        );
        if (!isMounted) return;
        setStatement(res.data || null);
      } catch {
        if (!isMounted) return;
        setStatement(null);
      } finally {
        if (isMounted) setStatementLoading(false);
      }
    };

    loadStatement();
    return () => {
      isMounted = false;
    };
  }, [leagueId, currencyType, seasonYear]);

  return (
    <div className={pageShell}>
      <div className={`${cardSurface} grid grid-cols-1 gap-4 md:grid-cols-3`}>
        <div>
          <label className="mb-2 block text-xs font-bold uppercase text-slate-600 dark:text-slate-400">
            Currency
          </label>
          <select
            className={inputBase}
            value={currencyType}
            onChange={(e) => setCurrencyType(e.target.value)}
          >
            {CURRENCY_OPTIONS.map((option) => (
              <option key={option.value || 'all'} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-2 block text-xs font-bold uppercase text-slate-600 dark:text-slate-400">
            Season Year
          </label>
          <input
            type="number"
            className={inputBase}
            placeholder="All years"
            value={seasonYear}
            onChange={(e) => setSeasonYear(e.target.value)}
          />
        </div>

        <div>
          <label className="mb-2 block text-xs font-bold uppercase text-slate-600 dark:text-slate-400">
            Balance
          </label>
          <div className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm font-bold text-slate-900 dark:text-white">
            {statement?.balance ?? 0}
          </div>
        </div>
      </div>

      <div className={tableSurface}>
        <table className="w-full text-sm text-slate-700 dark:text-slate-300">
          <thead className={tableHead}>
            <tr>
              <th className="px-3 py-2 text-left">Created</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-left">Direction</th>
              <th className="px-3 py-2 text-right">Amount</th>
              <th className="px-3 py-2 text-left">Currency</th>
              <th className="px-3 py-2 text-left">Reference</th>
              <th className="px-3 py-2 text-left">Notes</th>
            </tr>
          </thead>
          <tbody>
            {statementLoading ? (
              <tr>
                <td className="px-3 py-4 text-slate-500 dark:text-slate-400" colSpan={7}>
                  Loading statement...
                </td>
              </tr>
            ) : statement?.entries?.length ? (
              statement.entries.map((entry) => (
                <tr
                  key={entry.id}
                  className="border-t border-slate-300 dark:border-slate-800"
                >
                  <td className="px-3 py-2">{entry.created_at || '-'}</td>
                  <td className="px-3 py-2">{entry.transaction_type}</td>
                  <td className="px-3 py-2">{entry.direction}</td>
                  <td className="px-3 py-2 text-right">{entry.amount}</td>
                  <td className="px-3 py-2">{entry.currency_type}</td>
                  <td className="px-3 py-2">
                    {entry.reference_type || '-'}
                    {entry.reference_id ? `:${entry.reference_id}` : ''}
                  </td>
                  <td className="px-3 py-2">{entry.notes || '-'}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="px-3 py-4 text-slate-500 dark:text-slate-400" colSpan={7}>
                  No ledger entries found for the selected filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
