import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiChevronLeft, FiCheckCircle, FiAlertTriangle } from 'react-icons/fi';
import apiClient from '@api/client';

const clamp = (value, min, max) =>
  Math.max(min, Math.min(max, Number(value) || min));

export default function LineupRules() {
  const leagueId = localStorage.getItem('fantasyLeagueId');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [baseConfig, setBaseConfig] = useState(null);

  const [activeRosterSize, setActiveRosterSize] = useState(9);
  const [qbLimit, setQbLimit] = useState(3);
  const [rbLimit, setRbLimit] = useState(5);
  const [wrLimit, setWrLimit] = useState(5);
  const [teLimit, setTeLimit] = useState(3);
  const [kEnabled, setKEnabled] = useState(true);
  const [allowPartialLineup, setAllowPartialLineup] = useState(false);
  const [requireWeeklySubmit, setRequireWeeklySubmit] = useState(true);

  useEffect(() => {
    async function loadRules() {
      if (!leagueId) {
        setError('No active league selected.');
        setLoading(false);
        return;
      }

      try {
        const res = await apiClient.get(`/leagues/${leagueId}/settings`);
        const config = res.data;
        const slots = config.starting_slots || {};

        setBaseConfig(config);
        setActiveRosterSize(clamp(slots.ACTIVE_ROSTER_SIZE ?? 9, 5, 12));
        setQbLimit(clamp(slots.MAX_QB ?? 3, 1, 3));
        setRbLimit(clamp(slots.MAX_RB ?? 5, 1, 5));
        setWrLimit(clamp(slots.MAX_WR ?? 5, 1, 5));
        setTeLimit(clamp(slots.MAX_TE ?? 3, 1, 3));
        setKEnabled(Number(slots.MAX_K ?? 1) === 1);
        setAllowPartialLineup(Number(slots.ALLOW_PARTIAL_LINEUP ?? 0) === 1);
        setRequireWeeklySubmit(Number(slots.REQUIRE_WEEKLY_SUBMIT ?? 1) === 1);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load lineup rules.');
      } finally {
        setLoading(false);
      }
    }

    loadRules();
  }, [leagueId]);

  const totalCoreSlots = useMemo(
    () => 1 + 1 + 1 + 1 + (kEnabled ? 1 : 0) + 1,
    [kEnabled]
  );

  const saveRules = async () => {
    if (!baseConfig || !leagueId) return;

    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const nextStartingSlots = {
        ...(baseConfig.starting_slots || {}),
        ACTIVE_ROSTER_SIZE: clamp(activeRosterSize, 5, 12),
        MAX_QB: clamp(qbLimit, 1, 3),
        MAX_RB: clamp(rbLimit, 1, 5),
        MAX_WR: clamp(wrLimit, 1, 5),
        MAX_TE: clamp(teLimit, 1, 3),
        MAX_K: kEnabled ? 1 : 0,
        MAX_DEF: 1,
        ALLOW_PARTIAL_LINEUP: allowPartialLineup ? 1 : 0,
        REQUIRE_WEEKLY_SUBMIT: requireWeeklySubmit ? 1 : 0,
      };

      const payload = {
        ...baseConfig,
        starting_slots: nextStartingSlots,
      };

      await apiClient.put(`/leagues/${leagueId}/settings`, payload);
      setBaseConfig(payload);
      setSuccess('Lineup rules saved.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save lineup rules.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="text-white text-center mt-20 animate-pulse font-black uppercase tracking-widest">
        Loading Lineup Rules...
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto text-white min-h-screen">
      <div className="flex items-center justify-between mb-8 border-b border-slate-700 pb-5">
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Lineup Rules
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Configure league roster limits and lineup submission behavior.
          </p>
        </div>
        <Link
          to="/commissioner"
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm font-bold text-slate-300 hover:text-white"
        >
          <FiChevronLeft /> Back
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-800/60 bg-red-900/20 p-3 text-sm text-red-200 flex items-center gap-2">
          <FiAlertTriangle /> {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-lg border border-green-800/60 bg-green-900/20 p-3 text-sm text-green-200 flex items-center gap-2">
          <FiCheckCircle /> {success}
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl space-y-6">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide text-slate-400 mb-2">
            Total Active Roster Required (5 - 12)
          </label>
          <input
            type="number"
            min={5}
            max={12}
            value={activeRosterSize}
            onChange={(e) => setActiveRosterSize(clamp(e.target.value, 5, 12))}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <RuleInput
            label="QB (1-3)"
            value={qbLimit}
            min={1}
            max={3}
            onChange={setQbLimit}
          />
          <RuleInput
            label="RB (1-5)"
            value={rbLimit}
            min={1}
            max={5}
            onChange={setRbLimit}
          />
          <RuleInput
            label="WR (1-5)"
            value={wrLimit}
            min={1}
            max={5}
            onChange={setWrLimit}
          />
          <RuleInput
            label="TE (1-3)"
            value={teLimit}
            min={1}
            max={3}
            onChange={setTeLimit}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-3 text-sm flex items-center justify-between">
            <span>K Enabled (0 or 1)</span>
            <input
              type="checkbox"
              checked={kEnabled}
              onChange={(e) => setKEnabled(e.target.checked)}
            />
          </label>
          <div className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-3 text-sm flex items-center justify-between">
            <span>DEF</span>
            <span className="font-black">1 (fixed)</span>
          </div>
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-950 p-4 space-y-3">
          <ToggleRow
            label="Allow teams to submit below required threshold"
            checked={allowPartialLineup}
            onChange={setAllowPartialLineup}
          />
          <ToggleRow
            label="Require weekly lineup submission"
            checked={requireWeeklySubmit}
            onChange={setRequireWeeklySubmit}
          />
        </div>

        <div className="text-xs text-slate-400 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2">
          Minimum required core starters by position:{' '}
          <span className="font-black text-white">{totalCoreSlots}</span>
        </div>

        <div className="rounded-lg border border-slate-700 bg-slate-950 px-4 py-3">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-400 mb-2">
            Other ideas
          </p>
          <ul className="text-sm text-slate-300 list-disc ml-5 space-y-1">
            <li>
              Position-specific bench minimums (e.g., at least one backup RB).
            </li>
            <li>Auto-reject invalid lineups before weekly deadline.</li>
            <li>Optional FLEX enable/disable by league type.</li>
          </ul>
        </div>

        <div className="flex justify-end">
          <button
            onClick={saveRules}
            disabled={saving}
            className={`px-5 py-3 rounded-xl font-black uppercase tracking-wider text-sm ${saving ? 'bg-slate-800 text-slate-500' : 'bg-purple-600 hover:bg-purple-500 text-white'}`}
          >
            {saving ? 'Saving...' : 'Save Lineup Rules'}
          </button>
        </div>
      </div>
    </div>
  );
}

function RuleInput({ label, value, min, max, onChange }) {
  return (
    <div>
      <label className="block text-xs font-bold uppercase tracking-wide text-slate-400 mb-2">
        {label}
      </label>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(clamp(e.target.value, min, max))}
        className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
      />
    </div>
  );
}

function ToggleRow({ label, checked, onChange }) {
  return (
    <label className="text-sm text-slate-200 flex items-center justify-between">
      <span>{label}</span>
      <select
        value={checked ? 'Y' : 'N'}
        onChange={(e) => onChange(e.target.value === 'Y')}
        className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs font-bold"
      >
        <option value="Y">Y</option>
        <option value="N">N</option>
      </select>
    </label>
  );
}
