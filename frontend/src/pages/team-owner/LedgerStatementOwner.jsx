import { useEffect, useState } from 'react';
import apiClient from '@api/client';
import {
  StandardTable,
  StandardTableContainer,
  StandardTableHead,
  StandardTableRow,
  StandardTableStateRow,
} from '@components/table/TablePrimitives';
import {
  cardSurface,
  inputBase,
  pageShell,
  tableCell,
  tableCellNumeric,
  textMeta,
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
          <label className={`mb-2 block font-bold ${textMeta}`}>
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
          <label className={`mb-2 block font-bold ${textMeta}`}>
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
          <label className={`mb-2 block font-bold ${textMeta}`}>
            Balance
          </label>
          <div className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm font-bold text-slate-900 dark:text-white">
            {statement?.balance ?? 0}
          </div>
        </div>
      </div>

      <StandardTableContainer>
        <StandardTable>
          <StandardTableHead
            headers={[
              { key: 'created', label: 'Created', className: 'px-3 py-2 text-left' },
              { key: 'type', label: 'Type', className: 'px-3 py-2 text-left' },
              { key: 'direction', label: 'Direction', className: 'px-3 py-2 text-left' },
              { key: 'amount', label: 'Amount', className: 'px-3 py-2 text-right' },
              { key: 'currency', label: 'Currency', className: 'px-3 py-2 text-left' },
              { key: 'reference', label: 'Reference', className: 'px-3 py-2 text-left' },
              { key: 'notes', label: 'Notes', className: 'px-3 py-2 text-left' },
            ]}
          />
          <tbody>
            {statementLoading ? (
              <StandardTableStateRow colSpan={7}>Loading statement...</StandardTableStateRow>
            ) : statement?.entries?.length ? (
              statement.entries.map((entry) => (
                <StandardTableRow key={entry.id} className="hover:bg-transparent dark:hover:bg-transparent">
                  <td className={tableCell}>{entry.created_at || '-'}</td>
                  <td className={tableCell}>{entry.transaction_type}</td>
                  <td className={tableCell}>{entry.direction}</td>
                  <td className={tableCellNumeric}>{entry.amount}</td>
                  <td className={tableCell}>{entry.currency_type}</td>
                  <td className={tableCell}>
                    {entry.reference_type || '-'}
                    {entry.reference_id ? `:${entry.reference_id}` : ''}
                  </td>
                  <td className={tableCell}>{entry.notes || '-'}</td>
                </StandardTableRow>
              ))
            ) : (
              <StandardTableStateRow colSpan={7}>
                No ledger entries found for the selected filters.
              </StandardTableStateRow>
            )}
          </tbody>
        </StandardTable>
      </StandardTableContainer>
    </div>
  );
}
