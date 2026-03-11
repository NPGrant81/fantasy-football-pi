import { useCallback, useEffect, useMemo, useState } from 'react';
import apiClient from '@api/client';
import { normalizeApiError } from '@api/fetching';
import PageTemplate from '@components/layout/PageTemplate';
import { EmptyState, LoadingState } from '@components/common/AsyncState';
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
  textCaption,
  textMuted,
} from '@utils/uiStandards';
import { CALC_TYPE_LABEL } from '@utils/scoringRules';

const POSITION_OPTIONS = ['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

const CALCULATION_TYPES = [
  { value: 'flat_bonus', label: 'Flat Bonus', help: 'Adds/subtracts a fixed value when event condition is met.' },
  { value: 'per_unit', label: 'Per Unit', help: 'Multiplies stat amount by point value (e.g., passing yards * 0.04).' },
  { value: 'decimal', label: 'Decimal', help: 'Variant of per-unit scoring that allows fractional granularity.' },
  { value: 'ppr', label: 'PPR', help: 'Adds points per reception (full point per reception).' },
  { value: 'half_ppr', label: 'Half-PPR', help: 'Adds half-point per reception.' },
  { value: 'tiered', label: 'Tiered Range', help: 'Applies scoring by ranges using min/max bounds.' },
];

const SOURCE_OPTIONS = [
  { value: 'custom', label: 'Custom Rule Set (manual)' },
  { value: 'template', label: 'Template Applied Rule' },
  { value: 'imported', label: 'CSV Imported Rule' },
  { value: 'system', label: 'System Default Rule' },
];

const defaultRule = {
  category: '',
  event_name: '',
  description: '',
  range_min: '',
  range_max: '',
  point_value: '',
  calculation_type: 'flat_bonus',
  applicable_positions: ['ALL'],
  season_year: '',
  source: 'custom',
};

const defaultSimulatorStats = `{
  "passing_yards": 285,
  "passing_tds": 2,
  "interceptions": 1,
  "receptions": 0
}`;

function toNumberOrNull(value) {
  if (value === '' || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeRuleForForm(rule) {
  const positions = Array.isArray(rule.applicable_positions) && rule.applicable_positions.length
    ? rule.applicable_positions
    : ['ALL'];

  return {
    category: rule.category || '',
    event_name: rule.event_name || '',
    description: rule.description || '',
    range_min: rule.range_min ?? '',
    range_max: rule.range_max ?? '',
    point_value: rule.point_value ?? '',
    calculation_type: rule.calculation_type || 'flat_bonus',
    applicable_positions: positions,
    season_year: rule.season_year ?? '',
    source: rule.source || 'custom',
  };
}

function validateRuleForm(form) {
  const errors = {};
  if (!String(form.category || '').trim()) {
    errors.category = 'Category is required.';
  }
  if (!String(form.event_name || '').trim()) {
    errors.event_name = 'Event name is required.';
  }
  if (form.point_value === '' || form.point_value === null || form.point_value === undefined) {
    errors.point_value = 'Point value is required.';
  } else if (!Number.isFinite(Number(form.point_value))) {
    errors.point_value = 'Point value must be numeric.';
  }

  if (form.range_min !== '' && !Number.isFinite(Number(form.range_min))) {
    errors.range_min = 'Min must be numeric.';
  }
  if (form.range_max !== '' && !Number.isFinite(Number(form.range_max))) {
    errors.range_max = 'Max must be numeric.';
  }
  if (
    form.range_min !== '' &&
    form.range_max !== '' &&
    Number.isFinite(Number(form.range_min)) &&
    Number.isFinite(Number(form.range_max)) &&
    Number(form.range_min) > Number(form.range_max)
  ) {
    errors.range_max = 'Max must be greater than or equal to min.';
  }

  if (form.season_year !== '' && !Number.isInteger(Number(form.season_year))) {
    errors.season_year = 'Season year must be a whole number.';
  }

  return errors;
}

function buildRulePayload(form) {
  const selectedPositions = Array.isArray(form.applicable_positions)
    ? form.applicable_positions
    : [];

  const normalizedPositions = selectedPositions.includes('ALL')
    ? []
    : selectedPositions;

  return {
    category: String(form.category).trim(),
    event_name: String(form.event_name).trim(),
    description: String(form.description || '').trim() || null,
    ...(toNumberOrNull(form.range_min) !== null && { range_min: Number(form.range_min) }),
    ...(toNumberOrNull(form.range_max) !== null && { range_max: Number(form.range_max) }),
    point_value: Number(form.point_value),
    calculation_type: String(form.calculation_type || 'flat_bonus').trim(),
    applicable_positions: normalizedPositions,
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
  const [fieldErrors, setFieldErrors] = useState({});
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

  const [csvFile, setCsvFile] = useState(null);
  const [csvPreview, setCsvPreview] = useState([]);
  const [csvPreviewLoading, setCsvPreviewLoading] = useState(false);
  const [csvApplyLoading, setCsvApplyLoading] = useState(false);
  const [csvError, setCsvError] = useState('');
  const [csvReplaceExisting, setCsvReplaceExisting] = useState(false);
  const [csvSeasonYear, setCsvSeasonYear] = useState('');

  const selectedCalculationType = useMemo(
    () => CALCULATION_TYPES.find((type) => type.value === form.calculation_type),
    [form.calculation_type]
  );

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
      setError(normalizeApiError(err, 'Failed to load scoring rules.'));
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
    setFieldErrors({});
  };

  const onFormChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const togglePosition = (position) => {
    setForm((prev) => {
      const selected = new Set(prev.applicable_positions || []);
      if (position === 'ALL') {
        return { ...prev, applicable_positions: ['ALL'] };
      }

      selected.delete('ALL');
      if (selected.has(position)) {
        selected.delete(position);
      } else {
        selected.add(position);
      }

      if (!selected.size) {
        selected.add('ALL');
      }

      return { ...prev, applicable_positions: Array.from(selected) };
    });
  };

  const onSubmit = async (event) => {
    event.preventDefault();
    setMessage('');
    setError('');

    const validationErrors = validateRuleForm(form);
    setFieldErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      setError('Please resolve required and invalid fields before saving.');
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
      setError(normalizeApiError(err, 'Unable to save scoring rule.'));
    } finally {
      setSubmitting(false);
    }
  };

  const onEdit = (rule) => {
    setEditingRuleId(rule.id);
    setForm(normalizeRuleForForm(rule));
    setFieldErrors({});
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
      setError(normalizeApiError(err, 'Unable to deactivate scoring rule.'));
    }
  };

  const parseSimulatorPayload = () => {
    const parsed = JSON.parse(simStatsText);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('Stats payload must be a JSON object.');
    }
    return parsed;
  };

  const onRunPreview = async () => {
    setSimError('');
    setSimResult(null);
    let parsedStats;

    try {
      parsedStats = parseSimulatorPayload();
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
      setSimError(normalizeApiError(err, 'Unable to run scoring preview.'));
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
      setError(normalizeApiError(err, 'Unable to recalculate week scoring.'));
    } finally {
      setRecalcBusy(false);
    }
  };

  const readCsvFileText = async () => {
    if (!csvFile) {
      throw new Error('Please choose a CSV file before preview/apply.');
    }
    const text = await csvFile.text();
    if (!text.trim()) {
      throw new Error('Selected CSV file is empty.');
    }
    return text;
  };

  const onPreviewCsvImport = async () => {
    setCsvError('');
    setCsvPreview([]);
    setCsvPreviewLoading(true);
    try {
      const csvContent = await readCsvFileText();
      const payload = {
        csv_content: csvContent,
        season_year: csvSeasonYear === '' ? null : Number(csvSeasonYear),
        source_platform: 'imported',
      };
      const response = await apiClient.post('/scoring/import/preview', payload);
      const previewRules = Array.isArray(response?.data?.rules) ? response.data.rules : [];
      setCsvPreview(previewRules);
      setMessage(`CSV preview loaded (${previewRules.length} row(s)).`);
    } catch (err) {
      setCsvError(normalizeApiError(err, err?.message || 'Unable to preview CSV import.'));
    } finally {
      setCsvPreviewLoading(false);
    }
  };

  const onApplyCsvImport = async () => {
    setCsvError('');
    setCsvApplyLoading(true);
    try {
      const csvContent = await readCsvFileText();
      const payload = {
        csv_content: csvContent,
        season_year: csvSeasonYear === '' ? null : Number(csvSeasonYear),
        source_platform: 'imported',
        replace_existing_for_season: csvReplaceExisting,
      };
      const response = await apiClient.post('/scoring/import/apply', payload);
      const importedCount = Array.isArray(response.data) ? response.data.length : 0;
      setMessage(`Imported ${importedCount} scoring rule(s) from CSV.`);
      await fetchRules();
    } catch (err) {
      setCsvError(normalizeApiError(err, err?.message || 'Unable to apply CSV import.'));
    } finally {
      setCsvApplyLoading(false);
    }
  };

  const renderFieldError = (fieldName) => {
    if (!fieldErrors[fieldName]) return null;
    return <div className="mt-1 text-xs text-red-400">{fieldErrors[fieldName]}</div>;
  };

  return (
    <PageTemplate
      title="Manage Scoring Rules"
      subtitle="Commissioner controls for scoring rule creation, simulation previews, and retroactive week recalculation."
      className="min-h-screen"
    >

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
          <div className={textMuted}>{ruleCountLabel}</div>
        </div>

        <form onSubmit={onSubmit}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-3">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Category *
              </label>
              <input
                name="category"
                value={form.category}
                onChange={onFormChange}
                placeholder="Category"
                className={inputBase}
              />
              {renderFieldError('category')}
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Event Name *
              </label>
              <input
                name="event_name"
                value={form.event_name}
                onChange={onFormChange}
                placeholder="Event Name"
                className={inputBase}
              />
              {renderFieldError('event_name')}
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Point Value *
              </label>
              <input
                name="point_value"
                value={form.point_value}
                onChange={onFormChange}
                placeholder="Point Value"
                className={inputBase}
              />
              {renderFieldError('point_value')}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-3">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Description
              </label>
              <input
                name="description"
                value={form.description}
                onChange={onFormChange}
                placeholder="Description"
                className={inputBase}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Range Min
              </label>
              <input
                name="range_min"
                value={form.range_min}
                onChange={onFormChange}
                placeholder="Min"
                className={inputBase}
              />
              {renderFieldError('range_min')}
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Range Max
              </label>
              <input
                name="range_max"
                value={form.range_max}
                onChange={onFormChange}
                placeholder="Max"
                className={inputBase}
              />
              {renderFieldError('range_max')}
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Rule Type
              </label>
              <select
                name="calculation_type"
                value={form.calculation_type}
                onChange={onFormChange}
                className={inputBase}
              >
                {CALCULATION_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </select>
              <div className="mt-1 text-xs text-slate-500 dark:text-slate-400" title={selectedCalculationType?.help}>
                {selectedCalculationType?.help}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Applicable Positions
              </label>
              <div className="flex flex-wrap gap-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-2">
                {POSITION_OPTIONS.map((position) => {
                  const isSelected = (form.applicable_positions || []).includes(position);
                  return (
                    <button
                      key={position}
                      type="button"
                      className={`${isSelected ? buttonPrimary : buttonSecondary} px-3 py-1 text-xs`}
                      onClick={() => togglePosition(position)}
                    >
                      {position}
                    </button>
                  );
                })}
              </div>
              <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Choose one or more positions. Selecting ALL applies the rule league-wide.
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  Season Year
                </label>
                <input
                  name="season_year"
                  value={form.season_year}
                  onChange={onFormChange}
                  placeholder="e.g. 2026 (blank = all seasons)"
                  className={inputBase}
                />
                {renderFieldError('season_year')}
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  Source
                </label>
                <select
                  name="source"
                  value={form.source}
                  onChange={onFormChange}
                  className={inputBase}
                >
                  {SOURCE_OPTIONS.map((source) => (
                    <option key={source.value} value={source.value}>{source.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" className={buttonPrimary} disabled={submitting}>
              {submitting ? 'Saving...' : editingRuleId ? 'Update Rule' : 'Add Rule'}
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
        <h2 className="mb-3 text-lg font-bold text-slate-900 dark:text-white">CSV Import</h2>
        <p className={`mb-3 ${textMuted}`}>
          Bulk-load scoring rules from CSV, preview parsed rows, then apply to active rules.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end mb-3">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              CSV File
            </label>
            <input
              type="file"
              accept=".csv"
              onChange={(event) => setCsvFile(event.target.files?.[0] || null)}
              className={inputBase}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Season Year (optional)
            </label>
            <input
              value={csvSeasonYear}
              onChange={(event) => setCsvSeasonYear(event.target.value)}
              placeholder="e.g. 2026"
              className={inputBase}
            />
          </div>
          <label className={`inline-flex items-center gap-2 ${textMuted}`}>
            <input
              type="checkbox"
              checked={csvReplaceExisting}
              onChange={(event) => setCsvReplaceExisting(event.target.checked)}
            />
            Replace existing rules for season
          </label>
        </div>

        <div className="flex flex-wrap gap-2 mb-3">
          <button type="button" className={buttonSecondary} onClick={onPreviewCsvImport} disabled={csvPreviewLoading}>
            {csvPreviewLoading ? 'Previewing...' : 'Preview Import'}
          </button>
          <button type="button" className={buttonPrimary} onClick={onApplyCsvImport} disabled={csvApplyLoading}>
            {csvApplyLoading ? 'Applying...' : 'Apply Import'}
          </button>
        </div>

        {csvError ? <div className="text-sm text-red-400 mb-2">{csvError}</div> : null}

        {csvPreview.length > 0 ? (
          <StandardTableContainer>
            <StandardTable className="text-xs">
              <StandardTableHead
                headers={[
                  { key: 'category', label: 'Category' },
                  { key: 'event', label: 'Event' },
                  { key: 'type', label: 'Type' },
                  { key: 'points', label: 'Points' },
                  { key: 'positions', label: 'Positions' },
                ]}
              />
              <tbody>
                {csvPreview.slice(0, 10).map((row, idx) => (
                  <StandardTableRow key={`${row.event_name}-${idx}`} className="hover:bg-transparent dark:hover:bg-transparent">
                    <td className={tableCell}>{row.category}</td>
                    <td className={tableCell}>{row.event_name}</td>
                    <td className={tableCell}>{CALC_TYPE_LABEL[row.calculation_type] || row.calculation_type}</td>
                    <td className={tableCell}>{row.point_value}</td>
                    <td className={tableCell}>{(row.applicable_positions || []).join(', ') || 'ALL'}</td>
                  </StandardTableRow>
                ))}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        ) : null}
      </div>

      <div className={cardSurface}>
        <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">Current Rules</h2>
        {loading ? (
          <LoadingState />
        ) : rules.length === 0 ? (
          <EmptyState message="No scoring rules found." />
        ) : (
          <StandardTableContainer>
            <StandardTable>
              <StandardTableHead
                headers={[
                  { key: 'category', label: 'Category' },
                  { key: 'event', label: 'Event' },
                  { key: 'range', label: 'Range' },
                  { key: 'value', label: 'Value' },
                  { key: 'type', label: 'Type' },
                  { key: 'positions', label: 'Positions' },
                  { key: 'season', label: 'Season' },
                  { key: 'actions', label: 'Actions' },
                ]}
              />
              <tbody>
                {rules.map((rule) => (
                  <StandardTableRow key={rule.id}>
                    <td className={tableCell}>{rule.category}</td>
                    <td className={tableCell}>{rule.event_name}</td>
                    <td className={tableCell}>{rule.range_min}-{rule.range_max}</td>
                    <td className={tableCell}>{rule.point_value}</td>
                    <td className={tableCell}>{CALC_TYPE_LABEL[rule.calculation_type] || rule.calculation_type}</td>
                    <td className={tableCell}>{(rule.applicable_positions || []).join(', ') || 'ALL'}</td>
                    <td className={tableCell}>{rule.season_year || 'All seasons'}</td>
                    <td className={tableCell}>
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
                  </StandardTableRow>
                ))}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        )}
      </div>

      <div className={cardSurface}>
        <h2 className="mb-3 text-lg font-bold text-slate-900 dark:text-white">Scoring Preview Simulator</h2>
        <p className={`mb-3 ${textMuted}`}>
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
          <div className={`md:col-span-2 ${textMuted}`}>
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
          <div className="mt-4 rounded-lg border border-slate-300 dark:border-slate-700 p-3 space-y-2">
            <div className="text-sm font-semibold text-cyan-300">
              Total Preview Points: {simResult.points}
            </div>
            <div className={textCaption}>
              Rules evaluated: {simResult.rules_evaluated}
            </div>
            {Array.isArray(simResult.breakdown) && simResult.breakdown.length > 0 ? (
              <div className={textCaption}>
                Breakdown: {simResult.breakdown.map((item) => `${item.event_name}: ${item.points}`).join(' | ')}
              </div>
            ) : null}
            {simResult.rules_evaluated === 0 && (
              <div className={textMuted}>
                No scoring rules are configured for this league yet. Add rules above to see a point breakdown.
              </div>
            )}
          </div>
        )}
      </div>

      <div className={cardSurface}>
        <h2 className="mb-3 text-lg font-bold text-slate-900 dark:text-white">Retroactive Week Recalculation</h2>
        <p className={`mb-3 ${textMuted}`}>
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
    </PageTemplate>
  );
}
