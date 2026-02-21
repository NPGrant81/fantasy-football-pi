import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';

export default function ManageWaiverRules() {
  const [waiverDeadline, setWaiverDeadline] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  // Fetch current waiver deadline on mount
  useEffect(() => {
    async function fetchWaiverSettings() {
      try {
        // Assume leagueId is 1 for demo; replace with real league context
        const res = await apiClient.get('/leagues/1/settings');
        setWaiverDeadline(res.data.waiver_deadline || '');
      } catch (_err) {
        setMessage('Failed to load waiver rules');
      }
    }
    fetchWaiverSettings();
  }, []);

  // Handle form submit
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      // PATCH/PUT to update waiver_deadline (assume leagueId 1)
      await apiClient.put('/leagues/1/settings', {
        waiver_deadline: waiverDeadline,
      });
      setMessage('Waiver deadline updated!');
    } catch (_err) {
      setMessage('Failed to update waiver deadline');
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
        {/* Add more waiver rules here as needed */}
      </div>
    </div>
  );
}
// ...existing code...
