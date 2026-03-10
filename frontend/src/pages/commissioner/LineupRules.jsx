import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiChevronLeft, FiCheckCircle, FiAlertTriangle } from 'react-icons/fi';
import apiClient from '@api/client';
import { ErrorState, LoadingState } from '@components/common/AsyncState';
import PageTemplate from '@components/layout/PageTemplate';
import {
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  inputBase,
  pageShell,
} from '@utils/uiStandards';

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
  const [flexEnabled, setFlexEnabled] = useState(true);
  const [taxiSize, setTaxiSize] = useState(0);
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
        setFlexEnabled(Number(slots.MAX_FLEX ?? 1) === 1);
        setTaxiSize(clamp(slots.TAXI_SIZE ?? 0, 0, 5));
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
    () => 1 + 1 + 1 + 1 + (kEnabled ? 1 : 0) + 1 + (flexEnabled ? 1 : 0),
    [kEnabled, flexEnabled]
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
        MAX_FLEX: flexEnabled ? 1 : 0,
        TAXI_SIZE: clamp(taxiSize, 0, 5),
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
      <div className={pageShell}>
        <LoadingState message="Loading lineup rules..." className="mt-20" />
      </div>
    );
  }

  return (
    <PageTemplate
      title="Lineup Rules"
      subtitle="Configure league roster limits and lineup submission behavior."
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

      {error ? <ErrorState message={error} className="mb-4" /> : null}
      {success && (
        <div className="mb-4 rounded-lg border border-green-800/60 bg-green-900/20 p-3 text-sm text-green-200 flex items-center gap-2">
          <FiCheckCircle /> {success}
        </div>
      )}

      <div className={`${cardSurface} space-y-6`}>
        <div>
          <label className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            Total Active Roster Required (5 - 12)
          </label>
          <input
            type="number"
            min={5}
            max={12}
            value={activeRosterSize}
            onChange={(e) => setActiveRosterSize(clamp(e.target.value, 5, 12))}
            className={inputBase}
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

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <label className="flex items-center justify-between rounded-lg border border-slate-300 bg-white px-3 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
            <span>K Enabled (0 or 1)</span>
            <input
              type="checkbox"
              checked={kEnabled}
              onChange={(e) => setKEnabled(e.target.checked)}
            />
          </label>
          <label className="flex items-center justify-between rounded-lg border border-slate-300 bg-white px-3 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
            <span>Flex Enabled</span>
            <input
              type="checkbox"
              checked={flexEnabled}
              onChange={(e) => setFlexEnabled(e.target.checked)}
            />
          </label>
          <div className="flex items-center justify-between rounded-lg border border-slate-300 bg-white px-3 py-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
            <span>DEF</span>
            <span className="font-black text-slate-900 dark:text-white">
              1 (fixed)
            </span>
          </div>
        </div>

        <div className="rounded-lg border border-slate-300 bg-white p-4 space-y-3 dark:border-slate-700 dark:bg-slate-900">
          <div>
            <label className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
              Taxi Squad Size (0-5)
            </label>
            <input
              type="number"
              min={0}
              max={5}
              value={taxiSize}
              onChange={(e) => setTaxiSize(clamp(e.target.value, 0, 5))}
              className={inputBase}
            />
          </div>
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

        <div className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          Minimum required core starters by position:{' '}
          <span className="font-black text-slate-900 dark:text-white">
            {totalCoreSlots}
          </span>
        </div>

        <div className="rounded-lg border border-slate-300 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            Other ideas
          </p>
          <ul className="ml-5 list-disc space-y-1 text-sm text-slate-700 dark:text-slate-300">
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
            className={`${buttonPrimary} px-5 py-3 ${saving ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {saving ? 'Saving...' : 'Save Lineup Rules'}
          </button>
        </div>
      </div>
    </PageTemplate>
  );
}

function RuleInput({ label, value, min, max, onChange }) {
  return (
    <div>
      <label className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-600 dark:text-slate-400">
        {label}
      </label>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(clamp(e.target.value, min, max))}
        className={inputBase}
      />
    </div>
  );
}

function ToggleRow({ label, checked, onChange }) {
  return (
    <label className="flex items-center justify-between text-sm text-slate-700 dark:text-slate-200">
      <span>{label}</span>
      <select
        value={checked ? 'Y' : 'N'}
        onChange={(e) => onChange(e.target.value === 'Y')}
        className="rounded border border-slate-300 bg-white px-2 py-1 text-xs font-bold text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
      >
        <option value="Y">Y</option>
        <option value="N">N</option>
      </select>
    </label>
  );
}
