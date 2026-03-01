import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';
import {
  buttonPrimary,
  cardSurface,
  inputBase,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
  tableHead,
  tableSurface,
} from '@utils/uiStandards';

/* ignore-breakpoints */

export default function ManageWaiverRules() {
  const [waiverDeadline, setWaiverDeadline] = useState('');
  const [rosterSize, setRosterSize] = useState('');
  const [startingBudget, setStartingBudget] = useState('');
  const [waiverSystem, setWaiverSystem] = useState('FAAB');
  const [tieBreaker, setTieBreaker] = useState('standings');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [claims, setClaims] = useState([]); // waiver claim history for auditors
  const [claimsLoading, setClaimsLoading] = useState(false);
  const [budgets, setBudgets] = useState([]);
  const [budgetsLoading, setBudgetsLoading] = useState(false);

  // Fetch current waiver deadline on mount
  useEffect(() => {
    async function fetchWaiverSettings() {
      try {
        // Assume leagueId is 1 for demo; replace with real league context
        const res = await apiClient.get('/leagues/1/settings');
        setWaiverDeadline(res.data.waiver_deadline || '');
        setRosterSize(res.data.roster_size ? String(res.data.roster_size) : '');
        setStartingBudget(
          res.data.starting_waiver_budget
            ? String(res.data.starting_waiver_budget)
            : ''
        );
        setWaiverSystem(res.data.waiver_system || 'FAAB');
        setTieBreaker(res.data.waiver_tiebreaker || 'standings');
      } catch {
        setMessage('Failed to load waiver rules');
      }
    }
    fetchWaiverSettings();
    fetchClaims();
    fetchBudgets();
  }, []);

  // fetch historical waiver claims (commissioner only)
  const fetchClaims = async () => {
    setClaimsLoading(true);
    try {
      const res = await apiClient.get('/waivers/claims');
      setClaims(Array.isArray(res.data) ? res.data : []);
    } catch {
      // ignore failures for now
    } finally {
      setClaimsLoading(false);
    }
  };

  // fetch current budgets for league (commissioner view)
  const fetchBudgets = async () => {
    setBudgetsLoading(true);
    try {
      const res = await apiClient.get('/leagues/1/waiver-budgets');
      setBudgets(Array.isArray(res.data) ? res.data : []);
    } catch {
      setBudgets([]);
    } finally {
      setBudgetsLoading(false);
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
        roster_size: rosterSize ? Number(rosterSize) : undefined,
        starting_waiver_budget: startingBudget
          ? Number(startingBudget)
          : undefined,
        waiver_system: waiverSystem,
        waiver_tiebreaker: tieBreaker,
      };

      await apiClient.put('/leagues/1/settings', payload);
      setMessage('Waiver rules updated successfully.');
    } catch {
      setMessage('Failed to update waiver rules.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={pageShell}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Manage Waiver Rules</h1>
        <p className={pageSubtitle}>
          Configure waiver timing, budget, and tie-break behavior.
        </p>
      </div>

      <form onSubmit={handleSubmit} className={`${cardSurface} mb-0`}>
        <label
          htmlFor="waiver-deadline"
          className="block mb-2 text-sm font-bold text-slate-900 dark:text-white"
        >
          Waiver Deadline (ISO format or description)
        </label>
        <input
          id="waiver-deadline"
          type="text"
          className={`${inputBase} mb-4`}
          value={waiverDeadline}
          onChange={(e) => setWaiverDeadline(e.target.value)}
          placeholder="e.g. 2026-09-01T10:00:00Z or 'Wednesdays at 10am ET'"
        />
        <label
          htmlFor="starting-budget"
          className="block mb-2 text-sm font-bold text-slate-900 dark:text-white"
        >
          Starting FAAB Budget
        </label>
        <input
          id="starting-budget"
          type="number"
          min="0"
          className={`${inputBase} mb-4`}
          value={startingBudget}
          onChange={(e) => setStartingBudget(e.target.value)}
          placeholder="e.g. 100"
        />
        <label
          htmlFor="waiver-system"
          className="block mb-2 text-sm font-bold text-slate-900 dark:text-white"
        >
          Waiver System
        </label>
        <select
          id="waiver-system"
          value={waiverSystem}
          onChange={(e) => setWaiverSystem(e.target.value)}
          className={`${inputBase} mb-4`}
        >
          <option value="FAAB">FAAB</option>
          <option value="PRIORITY">Priority</option>
          <option value="BOTH">Both</option>
        </select>
        <label
          htmlFor="tiebreaker-rule"
          className="block mb-2 text-sm font-bold text-slate-900 dark:text-white"
        >
          Tie-breaker rule
        </label>
        <select
          id="tiebreaker-rule"
          value={tieBreaker}
          onChange={(e) => setTieBreaker(e.target.value)}
          className={`${inputBase} mb-4`}
        >
          <option value="standings">Lower standings (worse record)</option>
          <option value="priority">Waiver priority</option>
          <option value="timestamp">Earliest timestamp</option>
        </select>

        <label
          htmlFor="roster-size"
          className="block mb-2 text-sm font-bold text-slate-900 dark:text-white"
        >
          Roster Size Limit
        </label>
        <input
          id="roster-size"
          type="number"
          min="1"
          className={`${inputBase} mb-4`}
          value={rosterSize}
          onChange={(e) => setRosterSize(e.target.value)}
          placeholder="e.g. 14"
        />
        <button type="submit" className={buttonPrimary} disabled={loading}>
          {loading ? 'Saving...' : 'Update Waiver Rules'}
        </button>
        {message && <div className="mt-4 text-sm text-cyan-300">{message}</div>}
      </form>
      <div className={cardSurface}>
        <h2 className="text-lg font-bold mb-2 text-slate-900 dark:text-white">
          Current Waiver Rules
        </h2>
        <div className="text-slate-700 dark:text-slate-300">
          <strong>Waiver Deadline:</strong> {waiverDeadline || 'Not set'}
        </div>
        <div className="text-slate-700 dark:text-slate-300">
          <strong>Starting Budget:</strong> {startingBudget || 'Default'}
        </div>
        <div className="text-slate-700 dark:text-slate-300">
          <strong>Waiver System:</strong> {waiverSystem}
        </div>
        <div className="text-slate-700 dark:text-slate-300">
          <strong>Tie-breaker:</strong> {tieBreaker}
        </div>
        <div className="text-slate-700 dark:text-slate-300">
          <strong>Roster Size Limit:</strong> {rosterSize || 'Default'}
        </div>
      </div>

      <div className="mt-10">
        <h2 className="text-lg font-bold mb-4 text-slate-900 dark:text-white">
          Owner Budgets
        </h2>
        {budgetsLoading ? (
          <p className="text-slate-400">Loading budgets...</p>
        ) : budgets.length ? (
          <div className={`${tableSurface} mb-8`}>
            <table className="w-full text-sm text-slate-700 dark:text-slate-300">
              <thead className={tableHead}>
                <tr>
                  <th className="px-3 py-2">Owner ID</th>
                  <th className="px-3 py-2">Starting</th>
                  <th className="px-3 py-2">Remaining</th>
                  <th className="px-3 py-2">Spent</th>
                </tr>
              </thead>
              <tbody>
                {budgets.map((b) => (
                  <tr
                    key={b.owner_id}
                    className="border-t border-slate-300 dark:border-slate-800"
                  >
                    <td className="px-3 py-2">{b.owner_id}</td>
                    <td className="px-3 py-2">{b.starting_budget}</td>
                    <td className="px-3 py-2">{b.remaining_budget}</td>
                    <td className="px-3 py-2">{b.spent_budget}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-slate-500 dark:text-slate-400 italic mb-8">
            No budget data yet.
          </p>
        )}

        <h2 className="text-lg font-bold mb-4 text-slate-900 dark:text-white">
          Waiver Claim History
        </h2>
        {claimsLoading ? (
          <p className="text-slate-400">Loading history...</p>
        ) : claims.length ? (
          <div className={tableSurface}>
            <table className="w-full text-sm text-slate-700 dark:text-slate-300">
              <thead className={tableHead}>
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
                  <tr
                    key={c.id}
                    className="border-t border-slate-300 dark:border-slate-800"
                  >
                    <td className="px-3 py-2 text-xs font-mono text-slate-400">
                      {c.id /* no timestamp field yet */}
                    </td>
                    <td className="px-3 py-2">{c.username || c.user_id}</td>
                    <td className="px-3 py-2">
                      {c.player_name || c.player_id}
                    </td>
                    <td className="px-3 py-2">{c.drop_player_name || '-'}</td>
                    <td className="px-3 py-2">{c.bid_amount}</td>
                    <td className="px-3 py-2 capitalize">{c.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-slate-500 dark:text-slate-400 italic">
            No claims recorded yet.
          </p>
        )}
      </div>
    </div>
  );
}
// ...existing code...
