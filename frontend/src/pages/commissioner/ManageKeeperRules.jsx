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
    </PageTemplate>
  );
}
