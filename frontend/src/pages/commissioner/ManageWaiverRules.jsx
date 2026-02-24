import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';

export default function ManageWaiverRules() {
  const [waiverDeadline, setWaiverDeadline] = useState('');
  const [tradeDeadline, setTradeDeadline] = useState('');
  const [rosterSize, setRosterSize] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [claims, setClaims] = useState([]); // waiver claim history for auditors
  const [claimsLoading, setClaimsLoading] = useState(false);

  // Fetch current waiver deadline on mount
  useEffect(() => {
    async function fetchWaiverSettings() {
      try {
        // Assume leagueId is 1 for demo; replace with real league context
        const res = await apiClient.get('/leagues/1/settings');
        setWaiverDeadline(res.data.waiver_deadline || '');
        setTradeDeadline(res.data.trade_deadline || '');
        setRosterSize(res.data.roster_size ? String(res.data.roster_size) : '');
      } catch {
        setMessage('Failed to load waiver rules');
      }
    }
    fetchWaiverSettings();
    fetchClaims();
  }, []);

  // fetch historical waiver claims (commissioner only)
  const fetchClaims = async () => {
    setClaimsLoading(true);
    try {
      const res = await apiClient.get('/waivers/claims');
      setClaims(res.data || []);
    } catch {
      // ignore failures for now
    } finally {
      setClaimsLoading(false);
    }
  };

  // Handle form submit
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      // fetch existing settings to satisfy backend schema
      const existingRes = await apiClient.get('/leagues/1/settings');
      const existing = existingRes.data || {};
      const payload = {
        ...existing,
        waiver_deadline: waiverDeadline,
        trade_deadline: tradeDeadline,
        roster_size: rosterSize ? Number(rosterSize) : undefined,
      };

      await apiClient.put('/leagues/1/settings', payload);
      setMessage('Waiver rules updated successfully.');
    } catch (err) {
      setMessage('Failed to update waiver rules.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto text-white min-h-screen">
      <h1 className="text-3xl font-black mb-6">Manage Waiver Rules</h1>
      <form
        onSubmit={handleSubmit}
        className="mb-8 bg-slate-800 p-6 rounded-xl shadow"
      >
        <label className="block mb-2 font-bold">
          Waiver Deadline (ISO format or description)
        </label>
        <input
          type="text"
          className="w-full p-2 rounded bg-slate-900 text-white border border-slate-700 mb-4"
          value={waiverDeadline}
          onChange={(e) => setWaiverDeadline(e.target.value)}
          placeholder="e.g. 2026-09-01T10:00:00Z or 'Wednesdays at 10am ET'"
        />

        <label className="block mb-2 font-bold">
          Trade Deadline (ISO or description)
        </label>
        <input
          type="text"
          className="w-full p-2 rounded bg-slate-900 text-white border border-slate-700 mb-4"
          value={tradeDeadline}
          onChange={(e) => setTradeDeadline(e.target.value)}
          placeholder="e.g. 2026-09-10T12:00:00Z or 'Fridays at 5pm ET'"
        />

        <label className="block mb-2 font-bold">
          Roster Size Limit
        </label>
        <input
          type="number"
          min="1"
          className="w-full p-2 rounded bg-slate-900 text-white border border-slate-700 mb-4"
          value={rosterSize}
          onChange={(e) => setRosterSize(e.target.value)}
          placeholder="e.g. 14"
        />
        <button
          type="submit"
          className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-6 rounded"
          disabled={loading}
        >
          {loading ? 'Saving...' : 'Update Waiver Rules'}
        </button>
        {message && <div className="mt-4 text-blue-300">{message}</div>}
      </form>
      <div className="bg-slate-900 p-6 rounded-xl shadow">
        <h2 className="text-xl font-bold mb-2">Current Waiver Rules</h2>
        <div className="text-slate-300">
          <strong>Waiver Deadline:</strong> {waiverDeadline || 'Not set'}
        </div>
        <div className="text-slate-300">
          <strong>Trade Deadline:</strong> {tradeDeadline || 'Not set'}
        </div>
        <div className="text-slate-300">
          <strong>Roster Size Limit:</strong> {rosterSize || 'Default'}
        </div>
      </div>

      <div className="mt-10">
        <h2 className="text-xl font-bold mb-4">Waiver Claim History</h2>
        {claimsLoading ? (
          <p className="text-slate-400">Loading history...</p>
        ) : claims.length ? (
          <div className="overflow-x-auto bg-slate-900 rounded-xl p-4">
            <table className="w-full text-sm text-slate-300">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Time</th>
                  <th className="px-3 py-2">User</th>
                  <th className="px-3 py-2">Player</th>
                  <th className="px-3 py-2">Dropped</th>
                  <th className="px-3 py-2">Bid</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {claims.map((c) => (
                  <tr key={c.id} className="border-t border-slate-800">
                    <td className="px-3 py-2 text-xs font-mono text-slate-400">
                      {c.id /* no timestamp field yet */}
                    </td>
                    <td className="px-3 py-2">{c.username || c.user_id}</td>
                    <td className="px-3 py-2">{c.player_name || c.player_id}</td>
                    <td className="px-3 py-2">{c.drop_player_name || '-'}</td>
                    <td className="px-3 py-2">{c.bid_amount}</td>
                    <td className="px-3 py-2 capitalize">{c.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-slate-400 italic">No claims recorded yet.</p>
        )}
      </div>
    </div>
  );
}
// ...existing code...
