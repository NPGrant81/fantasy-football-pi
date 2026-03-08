import { useCallback, useEffect, useMemo, useState } from 'react';
import apiClient from '@api/client';
import {
  buttonDanger,
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  inputBase,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
  tableHead,
  tableSurface,
} from '@utils/uiStandards';

const defaultRule = {
  category: '',
  event_name: '',
  description: '',
  range_min: '',
  range_max: '',
  point_value: '',
  calculation_type: 'flat_bonus',
  applicable_positions: '',
  season_year: '',
  source: 'custom',
};

const defaultSimulatorStats = `{
  "passing_yards": 285,
  "passing_tds": 2,
  "interceptions": 1,
  "receptions": 0
}`;

function parsePositions(value) {
  return String(value || '')
    .split(',')
    .map((part) => part.trim().toUpperCase())
    .filter(Boolean);
}

function toNumberOrZero(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getErrorMessage(error, fallback) {
  return error?.response?.data?.detail || fallback;
}

function normalizeRuleForForm(rule) {
  return {
    category: rule.category || '',
    event_name: rule.event_name || '',
    description: rule.description || '',
    range_min: rule.range_min ?? '',
    range_max: rule.range_max ?? '',
    point_value: rule.point_value ?? '',
    calculation_type: rule.calculation_type || 'flat_bonus',
    applicable_positions: Array.isArray(rule.applicable_positions)
      ? rule.applicable_positions.join(', ')
      : '',
    season_year: rule.season_year ?? '',
    source: rule.source || 'custom',
  };
}

function buildRulePayload(form) {
  return {
    category: String(form.category).trim(),
    event_name: String(form.event_name).trim(),
    description: String(form.description || '').trim() || null,
    range_min: toNumberOrZero(form.range_min),
    range_max: toNumberOrZero(form.range_max),
    point_value: toNumberOrZero(form.point_value),
    calculation_type: String(form.calculation_type || 'flat_bonus').trim(),
    applicable_positions: parsePositions(form.applicable_positions),
    position_ids: [],
    season_year: form.season_year === '' ? null : Number(form.season_year),
    source: String(form.source || 'custom').trim() || 'custom',
    is_active: true,
  };
}

export default function ManageScoringRules() {
  const [rules, setRules] = useState([]);
  const [form, setForm] = useState(defaultRule);
  const [editingRuleId, setEditingRuleId] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [seasonFilter, setSeasonFilter] = useState('');

  const [simPosition, setSimPosition] = useState('QB');
  const [simStatsText, setSimStatsText] = useState(defaultSimulatorStats);
  const [simResult, setSimResult] = useState(null);
  const [simError, setSimError] = useState('');
  const [simLoading, setSimLoading] = useState(false);

  const [recalcSeason, setRecalcSeason] = useState(new Date().getFullYear());
  const [recalcWeek, setRecalcWeek] = useState(1);
  const [recalcBusy, setRecalcBusy] = useState(false);

  const ruleCountLabel = useMemo(() => {
    if (!rules.length) return 'No rules loaded';
    return `${rules.length} active rule${rules.length === 1 ? '' : 's'}`;
  }, [rules]);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      params.set('include_inactive', 'false');
      if (seasonFilter !== '') {
        params.set('season_year', String(seasonFilter));
      }

      const response = await apiClient.get(`/scoring/rules?${params.toString()}`);
      setRules(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load scoring rules.'));
    } finally {
      setLoading(false);
    }
  }, [seasonFilter]);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const resetForm = () => {
    setForm(defaultRule);
    setEditingRuleId(null);
  };

  const onFormChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const onSubmit = async (event) => {
    event.preventDefault();
    setMessage('');
    setError('');

    if (!form.category || !form.event_name || form.point_value === '') {
      setError('Category, event name, and point value are required.');
      return;
    }

    if (
      form.range_min !== '' &&
      form.range_max !== '' &&
      Number(form.range_min) > Number(form.range_max)
    ) {
      setError('Range min must be less than or equal to max.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = buildRulePayload(form);
      if (editingRuleId) {
        await apiClient.put(`/scoring/rules/${editingRuleId}`, payload);
        setMessage('Scoring rule updated.');
      } else {
        await apiClient.post('/scoring/rules', payload);
        setMessage('Scoring rule created.');
      }

      resetForm();
      await fetchRules();
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to save scoring rule.'));
    } finally {
      setSubmitting(false);
    }
  };

  const onEdit = (rule) => {
    setEditingRuleId(rule.id);
    setForm(normalizeRuleForForm(rule));
    setMessage('');
    setError('');
  };

  const onDelete = async (ruleId) => {
    setMessage('');
    setError('');
    try {
      await apiClient.delete(`/scoring/rules/${ruleId}`);
      if (editingRuleId === ruleId) {
        resetForm();
      }
      setMessage('Scoring rule deactivated.');
      await fetchRules();
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to deactivate scoring rule.'));
    }
  };

  const onRunPreview = async () => {
    setSimError('');
    setSimResult(null);
    let parsedStats;

    try {
      parsedStats = JSON.parse(simStatsText);
      if (!parsedStats || typeof parsedStats !== 'object' || Array.isArray(parsedStats)) {
        throw new Error('Stats must be a JSON object.');
      }
    } catch (err) {
      setSimError(err.message || 'Invalid JSON payload for simulator stats.');
      return;
    }

    setSimLoading(true);
    try {
      const payload = {
        position: simPosition,
        season_year: seasonFilter === '' ? null : Number(seasonFilter),
        stats: parsedStats,
      };
      const response = await apiClient.post('/scoring/calculate/player-preview', payload);
      setSimResult(response.data || null);
    } catch (err) {
      setSimError(getErrorMessage(err, 'Unable to run scoring preview.'));
    } finally {
      setSimLoading(false);
    }
  };

  const onRecalculateWeek = async () => {
    setError('');
    setMessage('');
    setRecalcBusy(true);
    try {
      const payload = {
        season: Number(recalcSeason),
        season_year: seasonFilter === '' ? null : Number(seasonFilter),
      };
      const response = await apiClient.post(
        `/scoring/calculate/weeks/${Number(recalcWeek)}/recalculate`,
        payload
      );
      setMessage(
        `Week ${recalcWeek} recalculated for ${response?.data?.recalculated_matchups ?? 0} matchup(s).`
      );
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to recalculate week scoring.'));
    } finally {
      setRecalcBusy(false);
    }
  };

  return (
    <div className={`${pageShell} min-h-screen`}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Manage Scoring Rules</h1>
        <p className={pageSubtitle}>
          Commissioner controls for scoring rule creation, simulation previews, and retroactive week recalculation.
        </p>
      </div>

      <div className={`${cardSurface} mb-0`}>
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Season Filter
            </label>
            <input
              name="season_filter"
              value={seasonFilter}
              onChange={(event) => setSeasonFilter(event.target.value)}
              placeholder="All seasons"
              className="w-full md:w-40 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
            />
          </div>
          <div className="text-sm text-slate-600 dark:text-slate-400">{ruleCountLabel}</div>
        </div>

        <form onSubmit={onSubmit}>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <input
              name="category"
              value={form.category}
              onChange={onFormChange}
              placeholder="Category"
              className={inputBase}
            />
            <input
              name="event_name"
              value={form.event_name}
              onChange={onFormChange}
              placeholder="Event Name"
              className={inputBase}
            />
            <input
              name="description"
              value={form.description}
              onChange={onFormChange}
              placeholder="Description"
              className={inputBase}
            />
            <div className="flex gap-2">
              <input
                name="range_min"
                value={form.range_min}
                onChange={onFormChange}
                placeholder="Min"
                className={`${inputBase} flex-1`}
              />
              <input
                name="range_max"
                value={form.range_max}
                onChange={onFormChange}
                placeholder="Max"
                className={`${inputBase} flex-1`}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
            <input
              name="point_value"
              value={form.point_value}
              onChange={onFormChange}
              placeholder="Point Value"
              className={inputBase}
            />
            <select
              name="calculation_type"
              value={form.calculation_type}
              onChange={onFormChange}
              className={inputBase}
            >
              <option value="flat_bonus">Flat Bonus</option>
              <option value="per_unit">Per Unit</option>
              <option value="decimal">Decimal</option>
              <option value="ppr">PPR</option>
              <option value="half_ppr">Half-PPR</option>
              <option value="tiered">Tiered</option>
            </select>
            <input
              name="applicable_positions"
              value={form.applicable_positions}
              onChange={onFormChange}
              placeholder="Positions (QB, RB, WR, TE, ALL)"
              className={inputBase}
            />
            <input
              name="season_year"
              value={form.season_year}
              onChange={onFormChange}
              placeholder="Season Year"
              className={inputBase}
            />
            <input
              name="source"
              value={form.source}
              onChange={onFormChange}
              placeholder="Source"
              className={inputBase}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" className={buttonPrimary} disabled={submitting}>
              {submitting
                ? 'Saving...'
                : editingRuleId
                ? 'Update Rule'
                : 'Add Rule'}
            </button>
            <button type="button" className={buttonSecondary} onClick={resetForm}>
              Clear Form
            </button>
          </div>
        </form>

        {error && <div className="mt-4 text-sm text-red-400">{error}</div>}
        {message && <div className="mt-4 text-sm text-cyan-300">{message}</div>}
      </div>

      <div className={cardSurface}>
        <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">Current Rules</h2>
        {loading ? (
          <div className="text-slate-600 dark:text-slate-400">Loading...</div>
        ) : rules.length === 0 ? (
          <div className="text-slate-600 dark:text-slate-400">No scoring rules found.</div>
        ) : (
          <div className={tableSurface}>
            <table className="w-full text-left text-sm text-slate-700 dark:text-slate-300">
              <thead className={tableHead}>
                <tr>
                  <th className="px-3 py-2">Category</th>
                  <th className="px-3 py-2">Event</th>
                  <th className="px-3 py-2">Range</th>
                  <th className="px-3 py-2">Value</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Positions</th>
                  <th className="px-3 py-2">Season</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr
                    key={rule.id}
                    className="border-t border-slate-300 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800/40"
                  >
                    <td className="px-3 py-2">{rule.category}</td>
                    <td className="px-3 py-2">{rule.event_name}</td>
                    <td className="px-3 py-2">{rule.range_min}-{rule.range_max}</td>
                    <td className="px-3 py-2">{rule.point_value}</td>
                    <td className="px-3 py-2">{rule.calculation_type}</td>
                    <td className="px-3 py-2">{(rule.applicable_positions || []).join(', ') || 'ALL'}</td>
                    <td className="px-3 py-2">{rule.season_year || 'Any'}</td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        className={`${buttonSecondary} mr-2 px-3 py-1 text-xs`}
                        onClick={() => onEdit(rule)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className={`${buttonDanger} px-3 py-1 text-xs`}
                        onClick={() => onDelete(rule.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className={cardSurface}>
        <h2 className="mb-3 text-lg font-bold text-slate-900 dark:text-white">Scoring Preview Simulator</h2>
        <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
          Validate stat payloads before publishing rule changes. Useful for player card and draft analyzer previews.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-3">
          <select
            className={inputBase}
            value={simPosition}
            onChange={(event) => setSimPosition(event.target.value)}
          >
            <option value="QB">QB</option>
            <option value="RB">RB</option>
            <option value="WR">WR</option>
            <option value="TE">TE</option>
            <option value="K">K</option>
            <option value="DST">DST</option>
            <option value="ALL">ALL</option>
          </select>
          <button type="button" className={buttonPrimary} onClick={onRunPreview} disabled={simLoading}>
            {simLoading ? 'Running...' : 'Run Preview'}
          </button>
          <div className="md:col-span-2 text-sm text-slate-600 dark:text-slate-400">
            Backend endpoint: <code>/scoring/calculate/player-preview</code>
          </div>
        </div>

        <textarea
          className={`${inputBase} min-h-40 font-mono text-xs`}
          value={simStatsText}
          onChange={(event) => setSimStatsText(event.target.value)}
        />

        {simError && <div className="mt-3 text-sm text-red-400">{simError}</div>}
        {simResult && (
          <div className="mt-4 rounded-lg border border-slate-300 dark:border-slate-700 p-3">
            <div className="mb-2 text-sm font-semibold text-cyan-300">
              Total Preview Points: {simResult.points}
            </div>
            <div className="text-xs text-slate-600 dark:text-slate-400">
              Rules evaluated: {simResult.rules_evaluated}
            </div>
          </div>
        )}
      </div>

      <div className={cardSurface}>
        <h2 className="mb-3 text-lg font-bold text-slate-900 dark:text-white">Retroactive Week Recalculation</h2>
        <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
          Recompute weekly matchup totals after approved mid-season scoring changes.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <input
            className={inputBase}
            value={recalcSeason}
            onChange={(event) => setRecalcSeason(event.target.value)}
            placeholder="Season"
          />
          <input
            className={inputBase}
            value={recalcWeek}
            onChange={(event) => setRecalcWeek(event.target.value)}
            placeholder="Week"
          />
          <button
            type="button"
            className={buttonSecondary}
            onClick={onRecalculateWeek}
            disabled={recalcBusy}
          >
            {recalcBusy ? 'Recalculating...' : 'Recalculate Week'}
          </button>
        </div>
      </div>
    </div>
  );
}
