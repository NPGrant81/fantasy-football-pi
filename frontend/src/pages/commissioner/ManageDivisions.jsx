import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiChevronLeft } from 'react-icons/fi';
import apiClient from '@api/client';
import { EmptyState, LoadingState } from '@components/common/AsyncState';
import PageTemplate from '@components/layout/PageTemplate';
import {
  StandardTable,
  StandardTableContainer,
  StandardTableHead,
  StandardTableRow,
} from '@components/table/TablePrimitives';
import {
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  inputBase,
  tableCell,
  textCaption,
  textMeta,
  textMuted,
} from '@utils/uiStandards';

function getDetailMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  try {
    return JSON.stringify(detail);
  } catch {
    return fallback;
  }
}

export default function ManageDivisions() {
  const leagueId = localStorage.getItem('fantasyLeagueId');

  const [season, setSeason] = useState(new Date().getUTCFullYear());
  const [ownerCount, setOwnerCount] = useState(0);

  const [enabled, setEnabled] = useState(false);
  const [divisionCount, setDivisionCount] = useState(2);
  const [assignmentMethod, setAssignmentMethod] = useState('heuristic');
  const [randomSeed, setRandomSeed] = useState('');
  const [names, setNames] = useState([]);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [message, setMessage] = useState('');

  const [preview, setPreview] = useState(null);
  const [reportDivisionName, setReportDivisionName] = useState('');
  const [reportReason, setReportReason] = useState('');

  const teamsPerDivision = useMemo(() => {
    if (!divisionCount || divisionCount <= 0) return 0;
    return Math.floor(ownerCount / divisionCount);
  }, [ownerCount, divisionCount]);

  const configValid = useMemo(() => {
    if (!enabled) return true;
    if (!divisionCount || divisionCount <= 0) return false;
    if (!ownerCount || ownerCount < 6) return false;
    if (ownerCount % divisionCount !== 0) return false;
    if (teamsPerDivision < 3) return false;
    if (names.length !== divisionCount) return false;

    const trimmed = names.map((n) => (n.name || '').trim());
    if (trimmed.some((n) => !n)) return false;
    if (trimmed.some((n) => n.length > 60)) return false;

    const set = new Set(trimmed.map((n) => n.toLocaleLowerCase()));
    return set.size === trimmed.length;
  }, [enabled, divisionCount, ownerCount, teamsPerDivision, names]);

  const ensureNamesLength = (count, existing = []) => {
    const safeCount = Number(count) || 0;
    const next = [];
    for (let idx = 0; idx < safeCount; idx += 1) {
      const current = existing[idx];
      next.push({
        name: current?.name || `Division ${idx + 1}`,
        order_index: idx,
      });
    }
    return next;
  };

  const loadContext = async (targetSeason = season) => {
    if (!leagueId) {
      setMessage('No active league selected.');
      return;
    }

    setLoading(true);
    setMessage('');
    try {
      const [ownersRes, configRes] = await Promise.all([
        apiClient.get(`/leagues/owners?league_id=${leagueId}`),
        apiClient.get(`/leagues/${leagueId}/divisions/config`, {
          params: { season: Number(targetSeason) },
        }),
      ]);

      const owners = Array.isArray(ownersRes.data) ? ownersRes.data : [];
      setOwnerCount(owners.length);

      const cfg = configRes.data || {};
      const cfgSeason = Number(cfg.season || targetSeason);
      const cfgEnabled = Boolean(cfg.divisions_enabled);
      const cfgCount = Number(cfg.division_count || 2);
      const cfgMethod = cfg.division_assignment_method || 'heuristic';

      setSeason(cfgSeason);
      setEnabled(cfgEnabled);
      setDivisionCount(cfgCount);
      setAssignmentMethod(cfgMethod);
      setRandomSeed(cfg.division_random_seed || '');

      const divisions = Array.isArray(cfg.divisions) ? cfg.divisions : [];
      const seedNames = divisions.length
        ? divisions
            .sort((a, b) => Number(a.order_index || 0) - Number(b.order_index || 0))
            .map((d, idx) => ({
              name: d.name || `Division ${idx + 1}`,
              order_index: Number(d.order_index || idx),
            }))
        : ensureNamesLength(cfgCount, cfg.proposal_from_previous_season || []);
      setNames(seedNames);
    } catch (err) {
      setMessage(getDetailMessage(err, 'Failed to load division settings.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadContext();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leagueId]);

  useEffect(() => {
    setNames((prev) => ensureNamesLength(divisionCount, prev));
  }, [divisionCount]);

  const onSaveConfig = async () => {
    if (!leagueId) return;
    if (!configValid) {
      setMessage('Current division configuration is invalid.');
      return;
    }

    setSaving(true);
    setMessage('');
    try {
      await apiClient.put(`/leagues/${leagueId}/divisions/config`, {
        season: Number(season),
        enabled,
        division_count: enabled ? Number(divisionCount) : null,
        assignment_method: assignmentMethod,
        random_seed: randomSeed || null,
        names: names.map((n, idx) => ({
          name: (n.name || '').trim(),
          order_index: idx,
        })),
      });
      setMessage('Division configuration saved.');
      await loadContext(season);
    } catch (err) {
      setMessage(getDetailMessage(err, 'Failed to save division configuration.'));
    } finally {
      setSaving(false);
    }
  };

  const onPreview = async () => {
    if (!leagueId) return;
    if (!enabled) {
      setMessage('Enable divisions before previewing assignments.');
      return;
    }

    setPreviewing(true);
    setMessage('');
    try {
      const res = await apiClient.post(
        `/leagues/${leagueId}/divisions/assignment-preview`,
        {
          season: Number(season),
          assignment_method: assignmentMethod,
          random_seed: randomSeed || null,
        }
      );
      setPreview(res.data || null);
      setMessage('Preview generated. Review confidence and imbalance before finalizing.');
    } catch (err) {
      setMessage(getDetailMessage(err, 'Failed to generate assignment preview.'));
    } finally {
      setPreviewing(false);
    }
  };

  const onFinalize = async () => {
    if (!leagueId) return;
    setFinalizing(true);
    setMessage('');
    try {
      await apiClient.post(`/leagues/${leagueId}/divisions/finalize`, {
        season: Number(season),
        assignment_method: assignmentMethod,
        random_seed: randomSeed || null,
      });
      setMessage('Divisions finalized for the selected season.');
      await loadContext(season);
    } catch (err) {
      setMessage(getDetailMessage(err, 'Failed to finalize divisions.'));
    } finally {
      setFinalizing(false);
    }
  };

  const onUndo = async () => {
    if (!leagueId) return;
    setUndoing(true);
    setMessage('');
    try {
      await apiClient.post(`/leagues/${leagueId}/divisions/undo-last`, {
        season: Number(season),
      });
      setMessage('Last finalized division assignment was undone.');
      await loadContext(season);
    } catch (err) {
      setMessage(getDetailMessage(err, 'Failed to undo last division assignment.'));
    } finally {
      setUndoing(false);
    }
  };

  const onReportName = async () => {
    if (!leagueId) return;
    if (!reportDivisionName.trim()) {
      setMessage('Enter a division name to report.');
      return;
    }

    try {
      await apiClient.post(`/leagues/${leagueId}/divisions/report-name`, {
        season: Number(season),
        division_name: reportDivisionName.trim(),
        reason: reportReason.trim() || null,
      });
      setMessage('Division name report queued for moderation review.');
      setReportDivisionName('');
      setReportReason('');
    } catch (err) {
      setMessage(getDetailMessage(err, 'Failed to submit division name report.'));
    }
  };

  return (
    <PageTemplate
      title="Manage Divisions"
      subtitle="Configure division structure, preview deterministic balancing, and finalize assignments."
      actions={
        <Link
          to="/commissioner"
          className={`${buttonSecondary} gap-2 px-3 py-2 text-sm no-underline`}
        >
          <FiChevronLeft /> Back
        </Link>
      }
    >

      {message && (
        <div className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-300">
          {message}
        </div>
      )}

      <div className={cardSurface}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block mb-2 text-sm font-bold text-slate-900 dark:text-white">
            Season
            </label>
            <input
              type="number"
              className={inputBase}
              value={season}
              onChange={(e) => setSeason(Number(e.target.value) || new Date().getUTCFullYear())}
              onBlur={() => loadContext(Number(season))}
            />
          </div>
          <div>
            <label className="block mb-2 text-sm font-bold text-slate-900 dark:text-white">
              League Owners
            </label>
            <input type="text" className={inputBase} value={ownerCount} readOnly />
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <input
            id="divisions-enabled"
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          <label htmlFor="divisions-enabled" className="text-sm font-bold text-slate-900 dark:text-white">
            Enable divisions for this season
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          <div>
            <label className="block mb-2 text-sm font-bold text-slate-900 dark:text-white">
              Division Count
            </label>
            <input
              type="number"
              min="1"
              className={inputBase}
              value={divisionCount}
              disabled={!enabled}
              onChange={(e) => setDivisionCount(Number(e.target.value) || 1)}
            />
          </div>
          <div>
            <label className="block mb-2 text-sm font-bold text-slate-900 dark:text-white">
              Assignment Method
            </label>
            <select
              className={inputBase}
              value={assignmentMethod}
              disabled={!enabled}
              onChange={(e) => setAssignmentMethod(e.target.value)}
            >
              <option value="manual" disabled>
                Manual (coming soon)
              </option>
              <option value="random">Random (seeded)</option>
              <option value="heuristic">Heuristic (deterministic)</option>
            </select>
          </div>
          <div>
            <label className="block mb-2 text-sm font-bold text-slate-900 dark:text-white">
              Random Seed (optional)
            </label>
            <input
              type="text"
              className={inputBase}
              value={randomSeed}
              disabled={!enabled}
              onChange={(e) => setRandomSeed(e.target.value)}
              placeholder="Stored for deterministic audits"
            />
          </div>
        </div>

        <div className="mt-4">
          <div className="mb-2 text-sm font-bold text-slate-900 dark:text-white">Division Names</div>
          <div className="space-y-2">
            {names.map((row, idx) => (
              <div key={`division-name-${idx}`} className="grid grid-cols-12 gap-2 items-center">
                <div className={`col-span-2 ${textMeta}`}>
                  #{idx + 1}
                </div>
                <input
                  type="text"
                  className="col-span-10 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-cyan-500/40"
                  value={row.name}
                  disabled={!enabled}
                  onChange={(e) => {
                    const next = [...names];
                    next[idx] = { ...next[idx], name: e.target.value };
                    setNames(next);
                  }}
                  maxLength={60}
                />
              </div>
            ))}
          </div>
        </div>

        <div className={`mt-5 ${textCaption}`}>
          {enabled ? (
            <>
              Teams per division: <strong>{teamsPerDivision || 0}</strong>. Rules: league must have at least 6
              owners, equal division sizes, and at least 3 owners per division.
            </>
          ) : (
            <>Divisions are currently disabled for this season.</>
          )}
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <button type="button" className={buttonPrimary} disabled={saving || !configValid} onClick={onSaveConfig}>
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
          <button type="button" className={buttonSecondary} disabled={previewing || !enabled || !configValid} onClick={onPreview}>
            {previewing ? 'Previewing...' : 'Preview Assignment'}
          </button>
          <button type="button" className={buttonSecondary} disabled={finalizing || !enabled || !configValid} onClick={onFinalize}>
            {finalizing ? 'Finalizing...' : 'Approve & Finalize'}
          </button>
          <button type="button" className={buttonSecondary} disabled={undoing} onClick={onUndo}>
            {undoing ? 'Undoing...' : 'Undo Last Finalize'}
          </button>
        </div>
      </div>

      <div className={cardSurface}>
        <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-3">Assignment Preview</h2>
        {!preview ? (
          <EmptyState message="No preview generated yet. Save configuration and click Preview Assignment." className={textMuted} />
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
              <div className="rounded-lg border border-slate-300 dark:border-slate-800 p-3">
                <div className={textMeta}>Method</div>
                <div className="text-sm font-bold text-slate-900 dark:text-white">{preview.assignment_method}</div>
              </div>
              <div className="rounded-lg border border-slate-300 dark:border-slate-800 p-3">
                <div className={textMeta}>Confidence</div>
                <div className="text-sm font-bold text-slate-900 dark:text-white">{preview.confidence_score}</div>
              </div>
              <div className="rounded-lg border border-slate-300 dark:border-slate-800 p-3">
                <div className={textMeta}>Imbalance</div>
                <div className="text-sm font-bold text-slate-900 dark:text-white">
                  {preview.imbalance_pct}%{preview.imbalance_warning ? ' (warning)' : ''}
                </div>
              </div>
            </div>

            <StandardTableContainer>
              <StandardTable>
                <StandardTableHead
                  headers={[
                    { key: 'division', label: 'Division' },
                    { key: 'teamIds', label: 'Team IDs' },
                    { key: 'avgStrength', label: 'Avg Strength' },
                  ]}
                />
                <tbody>
                  {(preview.assignments || []).map((row) => (
                    <StandardTableRow key={`preview-row-${row.division_index}`} className="hover:bg-transparent dark:hover:bg-transparent">
                      <td className={tableCell}>{row.division_index + 1}</td>
                      <td className={tableCell}>{(row.team_ids || []).join(', ') || '-'}</td>
                      <td className={tableCell}>{row.strength_avg ?? '-'}</td>
                    </StandardTableRow>
                  ))}
                </tbody>
              </StandardTable>
            </StandardTableContainer>
          </>
        )}
      </div>

      <div className={cardSurface}>
        <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-3">Report Division Name</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block mb-2 text-sm font-bold text-slate-900 dark:text-white">Division Name</label>
            <input
              type="text"
              className={inputBase}
              value={reportDivisionName}
              onChange={(e) => setReportDivisionName(e.target.value)}
              placeholder="Name to report"
            />
          </div>
          <div>
            <label className="block mb-2 text-sm font-bold text-slate-900 dark:text-white">Reason (optional)</label>
            <input
              type="text"
              className={inputBase}
              value={reportReason}
              onChange={(e) => setReportReason(e.target.value)}
              placeholder="Why this should be reviewed"
            />
          </div>
        </div>
        <div className="mt-4">
          <button type="button" className={buttonSecondary} onClick={onReportName}>
            Submit Name Report
          </button>
        </div>
      </div>

      {loading ? <LoadingState message="Loading division context..." className={textMuted} /> : null}
    </PageTemplate>
  );
}
