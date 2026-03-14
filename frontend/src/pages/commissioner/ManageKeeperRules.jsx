import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';
import { Link } from 'react-router-dom';
import { FiChevronLeft } from 'react-icons/fi';
import { EmptyState, LoadingState } from '@components/common/AsyncState';
import PageTemplate from '@components/layout/PageTemplate';
import {
  StandardTable,
  StandardTableContainer,
  StandardTableHead,
  StandardTableRow,
} from '@components/table/TablePrimitives';
import {
  buttonDanger,
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  inputBase,
  tableCell,
  textMuted,
} from '@utils/uiStandards';

export default function ManageKeeperRules() {
  const [maxKeepers, setMaxKeepers] = useState('');
  const [maxYears, setMaxYears] = useState('');
  const [deadline, setDeadline] = useState('');
  const [waiverPolicy, setWaiverPolicy] = useState(true);
  const [tradeDeadline, setTradeDeadline] = useState('');
  const [draftedOnly, setDraftedOnly] = useState(true);
  const [costType, setCostType] = useState('round');
  const [costInflation, setCostInflation] = useState('0');

  const [owners, setOwners] = useState([]);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [ownersLoading, setOwnersLoading] = useState(true);
  const [message, setMessage] = useState('');

  const [overrideOwnerId, setOverrideOwnerId] = useState('');
  const [overridePlayerName, setOverridePlayerName] = useState('');
  const [overrideNflTeam, setOverrideNflTeam] = useState('');
  const [overrideGsisId, setOverrideGsisId] = useState('');
  const [overrideKeepCost, setOverrideKeepCost] = useState('0');
  const [overrideYearsKept, setOverrideYearsKept] = useState('1');
  const [overrideSeason, setOverrideSeason] = useState('');

  const [historyFile, setHistoryFile] = useState(null);
  const [historyDryRun, setHistoryDryRun] = useState(true);
  const [historyResult, setHistoryResult] = useState(null);
  const [economicFile, setEconomicFile] = useState(null);
  const [economicDryRun, setEconomicDryRun] = useState(true);
  const [economicResult, setEconomicResult] = useState(null);

  useEffect(() => {
    fetchSettings();
    fetchOwners();
  }, []);

  const fetchSettings = async () => {
    setSettingsLoading(true);
    try {
      const res = await apiClient.get('/keepers/settings');
      const d = res.data || {};
      setMaxKeepers(d.max_keepers || '');
      setMaxYears(d.max_years_per_player || '');
      setDeadline(d.deadline_date || '');
      setWaiverPolicy(!!d.waiver_policy);
      setTradeDeadline(d.trade_deadline || '');
      setDraftedOnly(!!d.drafted_only);
      setCostType(d.cost_type || 'round');
      setCostInflation(
        d.cost_inflation != null ? String(d.cost_inflation) : '0'
      );
    } catch (e) {
      console.error('failed to load keeper settings', e);
      setMessage('Unable to fetch current settings');
    } finally {
      setSettingsLoading(false);
    }
  };

  const fetchOwners = async () => {
    setOwnersLoading(true);
    try {
      const res = await apiClient.get('/keepers/admin');
      setOwners(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      console.error('failed to load owner keeper lists', e);
      setOwners([]);
    } finally {
      setOwnersLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage('');
    try {
      const payload = {
        max_keepers: maxKeepers ? Number(maxKeepers) : undefined,
        max_years_per_player: maxYears ? Number(maxYears) : undefined,
        deadline_date: deadline || undefined,
        waiver_policy: waiverPolicy,
        trade_deadline: tradeDeadline || undefined,
        drafted_only: draftedOnly,
        cost_type: costType,
        cost_inflation: costInflation ? Number(costInflation) : undefined,
      };
      await apiClient.put('/keepers/settings', payload);
      setMessage('Keeper settings updated');
      fetchSettings();
    } catch (e) {
      console.error('error saving keeper settings', e);
      setMessage('Failed to update settings');
    }
  };

  const vetoOwner = async (ownerId) => {
    try {
      await apiClient.post(`/keepers/admin/${ownerId}/veto`);
      fetchOwners();
      setMessage(`Vetoed owner ${ownerId}`);
    } catch (e) {
      console.error('veto failed', e);
      setMessage('Veto failed');
    }
  };

  const resetLeague = async () => {
    if (!window.confirm('Clear all keepers for league?')) return;
    try {
      await apiClient.post('/keepers/admin/reset');
      fetchOwners();
      setMessage('All keepers cleared');
    } catch (e) {
      console.error('reset failed', e);
      setMessage('Reset failed');
    }
  };

  const applyManualOverride = async (e) => {
    e.preventDefault();
    setMessage('');
    setHistoryResult(null);

    if (!overrideOwnerId || !overridePlayerName || !overrideNflTeam) {
      setMessage('Owner, player name, and NFL team are required for override.');
      return;
    }

    try {
      await apiClient.post('/keepers/admin/override', {
        owner_id: Number(overrideOwnerId),
        player_name: overridePlayerName,
        nfl_team: overrideNflTeam,
        gsis_id: overrideGsisId || null,
        keep_cost: Number(overrideKeepCost || 0),
        years_kept_count: Number(overrideYearsKept || 1),
        season: overrideSeason ? Number(overrideSeason) : null,
      });
      setMessage('Commissioner keeper override applied.');
      setOverridePlayerName('');
      setOverrideNflTeam('');
      setOverrideGsisId('');
      setOverrideKeepCost('0');
      setOverrideYearsKept('1');
      setOverrideSeason('');
      fetchOwners();
    } catch (err) {
      console.error('override failed', err);
      setMessage(err.response?.data?.detail || 'Manual override failed');
    }
  };

  const downloadHistoryTemplate = async () => {
    try {
      const res = await apiClient.get('/keepers/admin/history-template', {
        responseType: 'text',
      });
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'keeper_history_template.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('template download failed', err);
      setMessage('Unable to download CSV template');
    }
  };

  const importHistoryCsv = async (e) => {
    e.preventDefault();
    setMessage('');
    setHistoryResult(null);

    if (!historyFile) {
      setMessage('Choose a CSV file before importing.');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('file', historyFile);
      const res = await apiClient.post(
        `/keepers/admin/import-history?dry_run=${historyDryRun ? 'true' : 'false'}`,
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
        }
      );
      setHistoryResult(res.data);
      setMessage(
        historyDryRun
          ? 'CSV dry-run complete. Review results below.'
          : 'CSV import complete.'
      );
      fetchOwners();
    } catch (err) {
      console.error('csv import failed', err);
      setMessage(err.response?.data?.detail || 'CSV import failed');
    }
  };

  const downloadEconomicTemplate = async () => {
    try {
      const res = await apiClient.get('/keepers/admin/economic-history-template', {
        responseType: 'text',
      });
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'economic_history_template.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('economic template download failed', err);
      setMessage('Unable to download economic CSV template');
    }
  };

  const importEconomicCsv = async (e) => {
    e.preventDefault();
    setMessage('');
    setEconomicResult(null);

    if (!economicFile) {
      setMessage('Choose an economic CSV file before importing.');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('file', economicFile);
      const res = await apiClient.post(
        `/keepers/admin/import-economic-history?dry_run=${economicDryRun ? 'true' : 'false'}`,
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
        }
      );
      setEconomicResult(res.data);
      setMessage(
        economicDryRun
          ? 'Economic CSV dry-run complete. Review results below.'
          : 'Economic CSV import complete.'
      );
      fetchOwners();
    } catch (err) {
      console.error('economic csv import failed', err);
      setMessage(err.response?.data?.detail || 'Economic CSV import failed');
    }
  };

  return (
    <PageTemplate
      title="Keeper Rules"
      subtitle="Configure keeper limits, deadlines, and commissioner overrides."
      actions={
        <Link
          to="/commissioner"
          className={`${buttonSecondary} gap-2 px-3 py-2 text-sm no-underline`}
        >
          <FiChevronLeft /> Back
        </Link>
      }
      className="min-h-screen"
    >

      <form onSubmit={handleSubmit} className={`${cardSurface} mb-0`}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="keeper-max-keepers"
              className="mb-2 block text-sm font-bold text-slate-900 dark:text-white"
            >
              Max Keepers Per Owner
            </label>
            <input
              id="keeper-max-keepers"
              type="number"
              min="0"
              className={inputBase}
              value={maxKeepers}
              onChange={(e) => setMaxKeepers(e.target.value)}
            />
          </div>
          <div>
            <label
              htmlFor="keeper-max-years"
              className="mb-2 block text-sm font-bold text-slate-900 dark:text-white"
            >
              Max Years Per Player
            </label>
            <input
              id="keeper-max-years"
              type="number"
              min="0"
              className={inputBase}
              value={maxYears}
              onChange={(e) => setMaxYears(e.target.value)}
            />
          </div>
          <div>
            <label
              htmlFor="keeper-deadline"
              className="mb-2 block text-sm font-bold text-slate-900 dark:text-white"
            >
              Keeper Deadline
            </label>
            <input
              id="keeper-deadline"
              type="text"
              className={inputBase}
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              placeholder="ISO date or description"
            />
          </div>
          <div>
            <label
              htmlFor="keeper-trade-deadline"
              className="mb-2 block text-sm font-bold text-slate-900 dark:text-white"
            >
              Trade Deadline
            </label>
            <input
              id="keeper-trade-deadline"
              type="text"
              className={inputBase}
              value={tradeDeadline}
              onChange={(e) => setTradeDeadline(e.target.value)}
              placeholder="ISO date or description"
            />
          </div>
          <div>
            <label
              htmlFor="keeper-cost-type"
              className="mb-2 block text-sm font-bold text-slate-900 dark:text-white"
            >
              Cost Type
            </label>
            <select
              id="keeper-cost-type"
              className={inputBase}
              value={costType}
              onChange={(e) => setCostType(e.target.value)}
            >
              <option value="round">Draft Round</option>
              <option value="value">Estimated Value</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          <div>
            <label
              htmlFor="keeper-cost-inflation"
              className="mb-2 block text-sm font-bold text-slate-900 dark:text-white"
            >
              Cost Inflation (add to cost)
            </label>
            <input
              id="keeper-cost-inflation"
              type="number"
              className={inputBase}
              value={costInflation}
              onChange={(e) => setCostInflation(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
            <input
              id="waiver-policy"
              type="checkbox"
              checked={waiverPolicy}
              onChange={(e) => setWaiverPolicy(e.target.checked)}
            />
            <label htmlFor="waiver-policy" className="font-bold">
              Waiver policy applied
            </label>
          </div>
          <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
            <input
              id="drafted-only"
              type="checkbox"
              checked={draftedOnly}
              onChange={(e) => setDraftedOnly(e.target.checked)}
            />
            <label htmlFor="drafted-only" className="font-bold">
              Must have been drafted
            </label>
          </div>
        </div>
        <div className="mt-6">
          <button type="submit" className={buttonPrimary}>
            {settingsLoading ? 'Saving...' : 'Update Settings'}
          </button>
          {message && (
            <div className="mt-4 text-sm text-cyan-300">{message}</div>
          )}
        </div>
      </form>

      <div className={cardSurface}>
        <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">
          Owner Keeper Lists
        </h2>
        <button className={`${buttonDanger} mb-4`} onClick={resetLeague}>
          Reset All Keepers
        </button>
        {ownersLoading ? (
          <LoadingState message="Loading keeper lists..." className={textMuted} />
        ) : owners.length ? (
          <StandardTableContainer>
            <StandardTable>
              <StandardTableHead
                headers={[
                  { key: 'owner', label: 'Owner' },
                  { key: 'selections', label: 'Selections' },
                  { key: 'actions', label: 'Actions' },
                ]}
              />
              <tbody>
                {owners.map((o) => (
                  <StandardTableRow key={o.owner_id} className="hover:bg-transparent dark:hover:bg-transparent">
                    <td className={tableCell}>{o.username || o.owner_id}</td>
                    <td className={tableCell}>{o.selections.length}</td>
                    <td className={tableCell}>
                      <button
                        className={`${buttonSecondary} px-3 py-1 text-xs`}
                        onClick={() => vetoOwner(o.owner_id)}
                      >
                        Veto
                      </button>
                    </td>
                  </StandardTableRow>
                ))}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        ) : (
          <EmptyState message="No keeper lists submitted yet." className={`${textMuted} italic`} />
        )}
      </div>

      <form onSubmit={applyManualOverride} className={cardSurface}>
        <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">
          Commissioner Manual Override
        </h2>
        <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
          Commissioner overrides supersede owner submissions and are stored as
          <span className="font-bold"> commish_override</span> entries.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="mb-2 block text-sm font-bold text-slate-900 dark:text-white">
              Owner
            </label>
            <select
              className={inputBase}
              value={overrideOwnerId}
              onChange={(e) => setOverrideOwnerId(e.target.value)}
            >
              <option value="">Select owner</option>
              {owners.map((o) => (
                <option key={o.owner_id} value={o.owner_id}>
                  {o.username || `Owner ${o.owner_id}`}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-bold text-slate-900 dark:text-white">
              Season (optional)
            </label>
            <input
              className={inputBase}
              type="number"
              value={overrideSeason}
              onChange={(e) => setOverrideSeason(e.target.value)}
              placeholder="Defaults to current draft year"
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-bold text-slate-900 dark:text-white">
              Player Name
            </label>
            <input
              className={inputBase}
              value={overridePlayerName}
              onChange={(e) => setOverridePlayerName(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-bold text-slate-900 dark:text-white">
              NFL Team
            </label>
            <input
              className={inputBase}
              value={overrideNflTeam}
              onChange={(e) => setOverrideNflTeam(e.target.value.toUpperCase())}
              placeholder="e.g., MIN"
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-bold text-slate-900 dark:text-white">
              GSIS ID (optional)
            </label>
            <input
              className={inputBase}
              value={overrideGsisId}
              onChange={(e) => setOverrideGsisId(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-bold text-slate-900 dark:text-white">
              Keeper Cost
            </label>
            <input
              className={inputBase}
              type="number"
              value={overrideKeepCost}
              onChange={(e) => setOverrideKeepCost(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-bold text-slate-900 dark:text-white">
              Years Kept Count
            </label>
            <input
              className={inputBase}
              type="number"
              min="0"
              value={overrideYearsKept}
              onChange={(e) => setOverrideYearsKept(e.target.value)}
            />
          </div>
        </div>
        <div className="mt-6">
          <button type="submit" className={buttonPrimary}>
            Apply Manual Override
          </button>
        </div>
      </form>

      <form onSubmit={importHistoryCsv} className={cardSurface}>
        <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">
          Keeper History CSV Import
        </h2>
        <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
          Match strategy: owner by username/team name, player by GSIS ID when
          present, otherwise by player name + NFL team. GSIS remains source of truth.
        </p>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className={buttonSecondary}
            onClick={downloadHistoryTemplate}
          >
            Download CSV Template
          </button>
          <label className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-200">
            <input
              type="checkbox"
              checked={historyDryRun}
              onChange={(e) => setHistoryDryRun(e.target.checked)}
            />
            Dry run (no DB writes)
          </label>
        </div>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setHistoryFile(e.target.files?.[0] || null)}
          className={`${inputBase} mb-4`}
        />
        <div>
          <button type="submit" className={buttonPrimary}>
            {historyDryRun ? 'Run CSV Dry-Run' : 'Import CSV History'}
          </button>
        </div>

        {historyResult && (
          <div className="mt-4 rounded-lg border border-slate-300 dark:border-slate-700 p-3 text-sm text-slate-700 dark:text-slate-200">
            <div>Processed: {historyResult.processed}</div>
            <div>Inserted: {historyResult.inserted}</div>
            <div>Updated: {historyResult.updated}</div>
            <div>Skipped: {historyResult.skipped}</div>
            {Array.isArray(historyResult.errors) && historyResult.errors.length > 0 && (
              <div className="mt-3">
                <div className="font-bold mb-1">Row issues:</div>
                <ul className="list-disc ml-5 space-y-1">
                  {historyResult.errors.slice(0, 20).map((err, idx) => (
                    <li key={`${err.row_number}-${idx}`}>
                      Row {err.row_number}: {err.detail}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </form>

      <form onSubmit={importEconomicCsv} className={cardSurface}>
        <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">
          Economic History CSV Import
        </h2>
        <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
          Import starting budgets, trades, and awards. Owner matching is canonical:
          username first, then exact team name fallback.
        </p>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className={buttonSecondary}
            onClick={downloadEconomicTemplate}
          >
            Download Economic Template
          </button>
          <label className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-200">
            <input
              type="checkbox"
              checked={economicDryRun}
              onChange={(e) => setEconomicDryRun(e.target.checked)}
            />
            Dry run (no DB writes)
          </label>
        </div>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setEconomicFile(e.target.files?.[0] || null)}
          className={`${inputBase} mb-4`}
        />
        <div>
          <button type="submit" className={buttonPrimary}>
            {economicDryRun ? 'Run Economic Dry-Run' : 'Import Economic History'}
          </button>
        </div>

        {economicResult && (
          <div className="mt-4 rounded-lg border border-slate-300 dark:border-slate-700 p-3 text-sm text-slate-700 dark:text-slate-200">
            <div>Processed: {economicResult.processed}</div>
            <div>Inserted: {economicResult.inserted}</div>
            <div>Updated: {economicResult.updated}</div>
            <div>Skipped: {economicResult.skipped}</div>
            {Array.isArray(economicResult.errors) && economicResult.errors.length > 0 && (
              <div className="mt-3">
                <div className="font-bold mb-1">Row issues:</div>
                <ul className="list-disc ml-5 space-y-1">
                  {economicResult.errors.slice(0, 20).map((err, idx) => (
                    <li key={`${err.row_number}-${idx}`}>
                      Row {err.row_number}: {err.detail}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </form>
    </PageTemplate>
  );
}
