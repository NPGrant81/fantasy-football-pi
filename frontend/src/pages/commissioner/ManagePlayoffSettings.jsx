import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiChevronLeft, FiPlus, FiX } from 'react-icons/fi';
import apiClient from '@api/client';
import { useActiveLeague } from '@context/LeagueContext';
import { LoadingState } from '@components/common/AsyncState';
import PageTemplate from '@components/layout/PageTemplate';
import {
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  inputBase,
  textMuted,
} from '@utils/uiStandards';

/* ignore-breakpoints */

const TIEBREAKER_OPTIONS = [
  { value: 'overall_record', label: 'Overall Record' },
  { value: 'points_for', label: 'Points For' },
  { value: 'points_against', label: 'Points Against (lower is better)' },
  { value: 'head_to_head', label: 'Head-to-Head' },
  { value: 'division_wins', label: 'Division Wins' },
  { value: 'random_draw', label: 'Random Draw (deterministic tiebreak)' },
];

export default function ManagePlayoffSettings() {
  const leagueId = useActiveLeague();

  const [qualifiers, setQualifiers] = useState('');
  const [reseed, setReseed] = useState(false);
  const [consolation, setConsolation] = useState(false);
  const [tiebreakers, setTiebreakers] = useState([]);
  const [nextTiebreaker, setNextTiebreaker] = useState('');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('success'); // 'success' | 'error'

  useEffect(() => {
    if (!leagueId) {
      setLoading(false);
      setMessage('No active league selected.');
      setMessageType('error');
      return;
    }

    setLoading(true);
    apiClient
      .get(`/playoffs/settings?league_id=${leagueId}`)
      .then((res) => {
        const d = res.data || {};
        setQualifiers(d.playoff_qualifiers != null ? String(d.playoff_qualifiers) : '');
        setReseed(Boolean(d.playoff_reseed));
        setConsolation(Boolean(d.playoff_consolation));
        setTiebreakers(Array.isArray(d.playoff_tiebreakers) ? d.playoff_tiebreakers : []);
      })
      .catch(() => {
        setMessage('Failed to load playoff settings.');
        setMessageType('error');
      })
      .finally(() => setLoading(false));
  }, [leagueId]);

  const addTiebreaker = () => {
    if (!nextTiebreaker) return;
    if (tiebreakers.includes(nextTiebreaker)) return;
    setTiebreakers((prev) => [...prev, nextTiebreaker]);
    setNextTiebreaker('');
  };

  const removeTiebreaker = (token) => {
    setTiebreakers((prev) => prev.filter((t) => t !== token));
  };

  const moveTiebreaker = (index, direction) => {
    const next = [...tiebreakers];
    const swap = index + direction;
    if (swap < 0 || swap >= next.length) return;
    [next[index], next[swap]] = [next[swap], next[index]];
    setTiebreakers(next);
  };

  const handleSave = async () => {
    if (!leagueId) return;
    setSaving(true);
    setMessage('');
    try {
      const payload = {
        playoff_qualifiers: Number(qualifiers) || undefined,
        playoff_reseed: reseed,
        playoff_consolation: consolation,
        playoff_tiebreakers: tiebreakers,
      };
      await apiClient.patch(`/playoffs/settings?league_id=${leagueId}`, payload);
      setMessage('Playoff settings saved.');
      setMessageType('success');
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const errText = Array.isArray(detail)
        ? detail.map((e) => e.msg || String(e)).join('; ')
        : detail || 'Failed to save settings.';
      setMessage(errText);
      setMessageType('error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingState message="Loading playoff settings…" className="mt-20" />;
  }

  const availableToAdd = TIEBREAKER_OPTIONS.filter((o) => !tiebreakers.includes(o.value));

  return (
    <PageTemplate
      title="Playoff Settings"
      subtitle="Configure playoff format, bracket structure, and tiebreaker priority."
    >
      <div className="mb-4">
        <Link
          to="/commissioner"
          className={`${buttonSecondary} inline-flex items-center gap-1`}
        >
          <FiChevronLeft /> Commissioner Panel
        </Link>
      </div>

      <div className={`${cardSurface} space-y-6`}>
        {/* Qualifier count */}
        <div className="space-y-1">
          <label className="block text-sm font-semibold text-slate-900 dark:text-slate-200">
            Playoff Teams
          </label>
          <p className={`${textMuted} text-xs`}>
            Number of teams that qualify for the postseason. Must be an even number.
          </p>
          <input
            type="number"
            min={2}
            step={2}
            value={qualifiers}
            onChange={(e) => setQualifiers(e.target.value)}
            className={`${inputBase} w-28`}
            data-testid="qualifiers-input"
          />
        </div>

        {/* Reseed toggle */}
        <div className="flex items-start gap-3">
          <input
            id="reseed"
            type="checkbox"
            checked={reseed}
            onChange={(e) => setReseed(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-slate-400 bg-white accent-cyan-500 dark:border-slate-600 dark:bg-slate-800"
            data-testid="reseed-checkbox"
          />
          <div>
            <label htmlFor="reseed" className="block text-sm font-semibold text-slate-900 dark:text-slate-200 cursor-pointer">
              Re-seed after each round
            </label>
            <p className={`${textMuted} text-xs`}>
              When enabled, the highest remaining seed always plays the lowest remaining seed
              instead of following the initial bracket draw.
            </p>
          </div>
        </div>

        {/* Consolation bracket toggle */}
        <div className="flex items-start gap-3">
          <input
            id="consolation"
            type="checkbox"
            checked={consolation}
            onChange={(e) => setConsolation(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-slate-400 bg-white accent-cyan-500 dark:border-slate-600 dark:bg-slate-800"
            data-testid="consolation-checkbox"
          />
          <div>
            <label htmlFor="consolation" className="block text-sm font-semibold text-slate-900 dark:text-slate-200 cursor-pointer">
              Enable Consolation Bracket (Toilet Bowl)
            </label>
            <p className={`${textMuted} text-xs`}>
              Non-playoff teams compete in a separate bracket. The last-place finisher earns
              the first draft pick next season.
            </p>
          </div>
        </div>

        {/* Tiebreaker priority chain */}
        <div className="space-y-2">
          <label className="block text-sm font-semibold text-slate-900 dark:text-slate-200">
            Tiebreaker Priority
          </label>
          <p className={`${textMuted} text-xs`}>
            Criteria applied in order when teams finish with equal records.
            Drag the order using the Up/Down buttons or remove unwanted criteria.
          </p>

          {tiebreakers.length === 0 && (
            <p className="text-xs italic text-slate-500">No tiebreakers configured — seed order will be used.</p>
          )}

          <ol className="space-y-1.5" data-testid="tiebreaker-list">
            {tiebreakers.map((token, index) => {
              const opt = TIEBREAKER_OPTIONS.find((o) => o.value === token);
              const label = opt ? opt.label : token;
              return (
                <li
                  key={token}
                  className="flex items-center gap-2 rounded border border-slate-300 bg-slate-100 px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-200"
                >
                  <span className="w-5 shrink-0 text-center text-xs font-bold text-slate-600 dark:text-slate-400">
                    {index + 1}
                  </span>
                  <span className="flex-1">{label}</span>
                  <button
                    onClick={() => moveTiebreaker(index, -1)}
                    disabled={index === 0}
                    className="text-slate-600 hover:text-slate-900 disabled:opacity-30 dark:text-slate-400 dark:hover:text-white"
                    aria-label="Move up"
                  >
                    ▲
                  </button>
                  <button
                    onClick={() => moveTiebreaker(index, 1)}
                    disabled={index === tiebreakers.length - 1}
                    className="text-slate-600 hover:text-slate-900 disabled:opacity-30 dark:text-slate-400 dark:hover:text-white"
                    aria-label="Move down"
                  >
                    ▼
                  </button>
                  <button
                    onClick={() => removeTiebreaker(token)}
                    className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                    aria-label={`Remove ${label}`}
                  >
                    <FiX />
                  </button>
                </li>
              );
            })}
          </ol>

          {availableToAdd.length > 0 && (
            <div className="flex items-center gap-2 pt-1">
              <select
                value={nextTiebreaker}
                onChange={(e) => setNextTiebreaker(e.target.value)}
                className={`${inputBase} flex-1`}
                data-testid="tiebreaker-select"
              >
                <option value="">— add tiebreaker —</option>
                {availableToAdd.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <button
                onClick={addTiebreaker}
                disabled={!nextTiebreaker}
                className={`${buttonSecondary} inline-flex items-center gap-1 disabled:opacity-40`}
                data-testid="add-tiebreaker-btn"
              >
                <FiPlus /> Add
              </button>
            </div>
          )}
        </div>

        {/* Message banner */}
        {message && (
          <p
            className={`rounded px-3 py-2 text-sm ${
              messageType === 'success'
                ? 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300'
                : 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300'
            }`}
            data-testid="settings-message"
          >
            {message}
          </p>
        )}

        {/* Save */}
        <div className="pt-2">
          <button
            onClick={handleSave}
            disabled={saving || !leagueId}
            className={`${buttonPrimary} disabled:opacity-50`}
            data-testid="save-btn"
          >
            {saving ? 'Saving…' : 'Save Playoff Settings'}
          </button>
        </div>
      </div>
    </PageTemplate>
  );
}
