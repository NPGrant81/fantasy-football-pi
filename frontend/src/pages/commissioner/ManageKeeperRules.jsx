import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';

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
    <div className="p-8 text-white min-h-screen">
      <h1 className="text-4xl font-black mb-6">Keeper Rules</h1>

      <form
        onSubmit={handleSubmit}
        className="mb-8 bg-slate-800 p-6 rounded-xl shadow"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block mb-2 font-bold">
              Max Keepers Per Owner
            </label>
            <input
              type="number"
              min="0"
              className="w-full p-2 rounded bg-slate-900 text-white border border-slate-700"
              value={maxKeepers}
              onChange={(e) => setMaxKeepers(e.target.value)}
            />
          </div>
          <div>
            <label className="block mb-2 font-bold">Max Years Per Player</label>
            <input
              type="number"
              min="0"
              className="w-full p-2 rounded bg-slate-900 text-white border border-slate-700"
              value={maxYears}
              onChange={(e) => setMaxYears(e.target.value)}
            />
          </div>
          <div>
            <label className="block mb-2 font-bold">Keeper Deadline</label>
            <input
              type="text"
              className="w-full p-2 rounded bg-slate-900 text-white border border-slate-700"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              placeholder="ISO date or description"
            />
          </div>
          <div>
            <label className="block mb-2 font-bold">Trade Deadline</label>
            <input
              type="text"
              className="w-full p-2 rounded bg-slate-900 text-white border border-slate-700"
              value={tradeDeadline}
              onChange={(e) => setTradeDeadline(e.target.value)}
              placeholder="ISO date or description"
            />
          </div>
          <div>
            <label className="block mb-2 font-bold">Cost Type</label>
            <select
              className="w-full p-2 rounded bg-slate-900 text-white border border-slate-700"
              value={costType}
              onChange={(e) => setCostType(e.target.value)}
            >
              <option value="round">Draft Round</option>
              <option value="value">Estimated Value</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          <div>
            <label className="block mb-2 font-bold">
              Cost Inflation (add to cost)
            </label>
            <input
              type="number"
              className="w-full p-2 rounded bg-slate-900 text-white border border-slate-700"
              value={costInflation}
              onChange={(e) => setCostInflation(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
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
          <div className="flex items-center gap-2">
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
          <button
            type="submit"
            className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-6 rounded"
          >
            {settingsLoading ? 'Saving...' : 'Update Settings'}
          </button>
          {message && <div className="mt-4 text-blue-300">{message}</div>}
        </div>
      </form>

      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-4">Owner Keeper Lists</h2>
        <button
          className="bg-red-600 hover:bg-red-500 text-white font-bold py-2 px-4 rounded mb-4"
          onClick={resetLeague}
        >
          Reset All Keepers
        </button>
        {ownersLoading ? (
          <p className="text-slate-400">Loading...</p>
        ) : owners.length ? (
          <div className="overflow-x-auto bg-slate-900 rounded-xl p-4">
            <table className="w-full text-sm text-slate-300">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Owner</th>
                  <th className="px-3 py-2">Selections</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {owners.map((o) => (
                  <tr key={o.owner_id} className="border-t border-slate-800">
                    <td className="px-3 py-2">{o.username || o.owner_id}</td>
                    <td className="px-3 py-2">{o.selections.length}</td>
                    <td className="px-3 py-2">
                      <button
                        className="bg-yellow-600 hover:bg-yellow-500 text-black font-bold py-1 px-3 rounded"
                        onClick={() => vetoOwner(o.owner_id)}
                      >
                        Veto
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-slate-400 italic">
            No keeper lists submitted yet.
          </p>
        )}
      </div>
    </div>
  );
}
