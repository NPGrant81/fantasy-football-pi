import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiChevronLeft } from 'react-icons/fi';
import apiClient from '@api/client';
import { useActiveLeague } from '@context/LeagueContext';
import PageTemplate from '@components/layout/PageTemplate';
import {
  StandardTable,
  StandardTableContainer,
  StandardTableHead,
  StandardTableRow,
  StandardTableStateRow,
} from '@components/table/TablePrimitives';
import {
  buttonSecondary,
  cardSurface,
  inputBase,
  tableCell,
  tableCellNumeric,
  textMeta,
} from '@utils/uiStandards';

const CURRENCY_OPTIONS = [
  { value: '', label: 'All currencies' },
  { value: 'DRAFT_DOLLARS', label: 'Draft Dollars' },
  { value: 'FAAB', label: 'FAAB' },
];

export default function LedgerStatement() {
  const leagueId = useActiveLeague();
  const [owners, setOwners] = useState([]);
  const [ownerId, setOwnerId] = useState('');
  const [currencyType, setCurrencyType] = useState('');
  const [seasonYear, setSeasonYear] = useState('');
  const [loading, setLoading] = useState(true);
  const [statementLoading, setStatementLoading] = useState(false);
  const [statement, setStatement] = useState(null);

  useEffect(() => {
    if (!leagueId) return;

    let isMounted = true;
    const loadInitial = async () => {
      setLoading(true);
      try {
        const ownerRes = await apiClient.get(`/leagues/owners?league_id=${leagueId}`);
        const rows = Array.isArray(ownerRes.data) ? ownerRes.data : [];
        if (!isMounted) return;
        setOwners(rows);
        if (rows.length > 0) {
          setOwnerId(String(rows[0].id));
        }
      } catch {
        if (!isMounted) return;
        setOwners([]);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    loadInitial();
    return () => {
      isMounted = false;
    };
  }, [leagueId]);

  useEffect(() => {
    if (!leagueId || !ownerId) return;

    let isMounted = true;
    const loadStatement = async () => {
      setStatementLoading(true);
      try {
        const params = new URLSearchParams();
        params.append('owner_id', ownerId);
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
  }, [leagueId, ownerId, currencyType, seasonYear]);

  const ownerName = useMemo(() => {
    const selected = owners.find((o) => String(o.id) === String(ownerId));
    return selected?.team_name || selected?.username || 'Owner';
  }, [owners, ownerId]);

  return (
    <PageTemplate
      title="Ledger Statement"
      subtitle="Auditable transaction ledger for a selected owner."
      actions={
        <Link
          to="/commissioner"
          className={`${buttonSecondary} gap-2 px-3 py-2 text-sm no-underline`}
        >
          <FiChevronLeft /> Back
        </Link>
      }
    >

      <div className={`${cardSurface} grid grid-cols-1 gap-4 md:grid-cols-4`}>
        <div>
          <label className="mb-2 block text-xs font-bold uppercase text-slate-600 dark:text-slate-400">
            Owner
          </label>
          <select
            className={inputBase}
            value={ownerId}
            onChange={(e) => setOwnerId(e.target.value)}
            disabled={loading || owners.length === 0}
          >
            {owners.map((owner) => (
              <option key={owner.id} value={owner.id}>
                {owner.team_name || owner.username}
              </option>
            ))}
          </select>
        </div>

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

        <div className="flex items-end">
          <button
            className={buttonSecondary}
            onClick={() => {
              setCurrencyType('');
              setSeasonYear('');
            }}
          >
            Clear Filters
          </button>
        </div>
      </div>

      <div className={`${cardSurface} grid grid-cols-1 gap-4 md:grid-cols-3`}>
        <div>
          <div className={textMeta}>
            Owner
          </div>
          <div className="text-lg font-bold text-slate-900 dark:text-white">
            {ownerName}
          </div>
        </div>
        <div>
          <div className={textMeta}>
            Balance
          </div>
          <div className="text-lg font-bold text-slate-900 dark:text-white">
            {statement?.balance ?? 0}
          </div>
        </div>
        <div>
          <div className={textMeta}>
            Entries
          </div>
          <div className="text-lg font-bold text-slate-900 dark:text-white">
            {statement?.entry_count ?? 0}
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
    </PageTemplate>
  );
}
