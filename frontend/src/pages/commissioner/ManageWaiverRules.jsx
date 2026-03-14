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
  buttonSecondary,
  buttonPrimary,
  cardSurface,
  inputBase,
  tableCell,
  textMuted,
} from '@utils/uiStandards';

/* ignore-breakpoints */

export default function ManageWaiverRules() {
  const leagueId = localStorage.getItem('fantasyLeagueId');
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
      if (!leagueId) {
        setMessage('No active league selected.');
        return;
      }
      try {
        const res = await apiClient.get(`/leagues/${leagueId}/settings`);
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
  }, [leagueId]);

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
    if (!leagueId) {
      setBudgets([]);
      return;
    }
    setBudgetsLoading(true);
    try {
      const res = await apiClient.get(`/leagues/${leagueId}/waiver-budgets`);
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
    if (!leagueId) {
      setMessage('No active league selected.');
      return;
    }
    setLoading(true);
    setMessage('');
    try {
      // fetch existing settings to satisfy backend schema
      const existingRes = await apiClient.get(`/leagues/${leagueId}/settings`);
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

      await apiClient.put(`/leagues/${leagueId}/settings`, payload);
      setMessage('Waiver rules updated successfully.');
      fetchBudgets();
    } catch {
      setMessage('Failed to update waiver rules.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageTemplate
      title="Manage Waiver Rules"
      subtitle="Configure waiver timing, budget, and tie-break behavior."
      actions={
        <Link
          to="/commissioner"
          className={`${buttonSecondary} gap-2 px-3 py-2 text-sm no-underline`}
        >
          <FiChevronLeft /> Back
        </Link>
      }
    >

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
        <div className={textMuted}>
          <strong>Waiver Deadline:</strong> {waiverDeadline || 'Not set'}
        </div>
        <div className={textMuted}>
          <strong>Starting Budget:</strong> {startingBudget || 'Default'}
        </div>
        <div className={textMuted}>
          <strong>Waiver System:</strong> {waiverSystem}
        </div>
        <div className={textMuted}>
          <strong>Tie-breaker:</strong> {tieBreaker}
        </div>
        <div className={textMuted}>
          <strong>Roster Size Limit:</strong> {rosterSize || 'Default'}
        </div>
      </div>

      <div className="mt-10">
        <h2 className="text-lg font-bold mb-4 text-slate-900 dark:text-white">
          Owner Budgets
        </h2>
        {budgetsLoading ? (
          <LoadingState message="Loading budgets..." className={textMuted} />
        ) : budgets.length ? (
          <StandardTableContainer className="mb-8">
            <StandardTable>
              <StandardTableHead
                headers={[
                  { key: 'owner', label: 'Owner ID' },
                  { key: 'starting', label: 'Starting' },
                  { key: 'remaining', label: 'Remaining' },
                  { key: 'spent', label: 'Spent' },
                ]}
              />
              <tbody>
                {budgets.map((b) => (
                  <StandardTableRow key={b.owner_id} className="hover:bg-transparent dark:hover:bg-transparent">
                    <td className={tableCell}>{b.owner_id}</td>
                    <td className={tableCell}>{b.starting_budget}</td>
                    <td className={tableCell}>{b.remaining_budget}</td>
                    <td className={tableCell}>{b.spent_budget}</td>
                  </StandardTableRow>
                ))}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        ) : (
          <EmptyState message="No budget data yet." className={`${textMuted} mb-8`} />
        )}

        <h2 className="text-lg font-bold mb-4 text-slate-900 dark:text-white">
          Waiver Claim History
        </h2>
        {claimsLoading ? (
          <LoadingState message="Loading history..." className={textMuted} />
        ) : claims.length ? (
          <StandardTableContainer>
            <StandardTable>
              <StandardTableHead
                headers={[
                  { key: 'time', label: 'Time' },
                  { key: 'user', label: 'User' },
                  { key: 'player', label: 'Player' },
                  { key: 'dropped', label: 'Dropped' },
                  { key: 'bid', label: 'Bid' },
                  { key: 'status', label: 'Status' },
                ]}
              />
              <tbody>
                {claims.map((c) => (
                  <StandardTableRow key={c.id} className="hover:bg-transparent dark:hover:bg-transparent">
                    <td className="px-3 py-2 text-xs font-mono text-slate-400">
                      {c.id /* no timestamp field yet */}
                    </td>
                    <td className={tableCell}>{c.username || c.user_id}</td>
                    <td className={tableCell}>
                      {c.player_name || c.player_id}
                    </td>
                    <td className={tableCell}>{c.drop_player_name || '-'}</td>
                    <td className={tableCell}>{c.bid_amount}</td>
                    <td className={`${tableCell} capitalize`}>{c.status}</td>
                  </StandardTableRow>
                ))}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        ) : (
          <EmptyState message="No claims recorded yet." className={textMuted} />
        )}
      </div>
    </PageTemplate>
  );
}
// ...existing code...
