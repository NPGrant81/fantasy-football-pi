import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { FiChevronLeft, FiX, FiCheck, FiXCircle } from 'react-icons/fi';
import { useActiveLeague } from '@context/LeagueContext';
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
  textMuted,
  layerModal,
  layerBackdrop,
} from '@utils/uiStandards';
import {
  fetchPendingTrades,
  fetchTradeDetail,
  fetchTradeHistory,
  fetchTradeWindowSettings,
  saveTradeWindowSettings,
  approveTrade,
  rejectTrade,
} from '@api/tradesApi';

/* ignore-breakpoints */

const TIMEZONES = [
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Phoenix',
  'America/Anchorage',
  'Pacific/Honolulu',
  'UTC',
];

const summarizeAssets = (assets = []) => {
  if (!Array.isArray(assets) || assets.length === 0) return 'None';
  return assets
    .map((a) => {
      if (a.asset_type === 'PLAYER') return a.player_name || `Player #${a.player_id}`;
      if (a.asset_type === 'DRAFT_PICK')
        return `Pick #${a.draft_pick_id}${a.season_year ? ` (${a.season_year})` : ''}`;
      if (a.asset_type === 'DRAFT_DOLLARS') return `$${Number(a.amount || 0)}`;
      return a.asset_type;
    })
    .join(', ');
};

const fmtDt = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

// ── Trade Window Settings Panel ───────────────────────────────────────────────

function TradeWindowSettings({ leagueId }) {
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState({ trade_start_at: '', trade_end_at: '', timezone: 'America/New_York', is_active: false });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!leagueId) return;
    setLoading(true);
    setError('');
    try {
      const data = await fetchTradeWindowSettings(leagueId);
      setSettings(data);
      setForm({
        trade_start_at: data.trade_start_at ? data.trade_start_at.slice(0, 16) : '',
        trade_end_at: data.trade_end_at ? data.trade_end_at.slice(0, 16) : '',
        timezone: data.timezone || 'America/New_York',
        is_active: Boolean(data.is_active),
      });
    } catch {
      setError('Trade window settings unavailable (feature may not be enabled yet).');
    } finally {
      setLoading(false);
    }
  }, [leagueId]);

  useEffect(() => { load(); }, [load]);

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setMessage('');
    setError('');
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setMessage('');
    setError('');
    if (form.trade_start_at && form.trade_end_at && form.trade_start_at >= form.trade_end_at) {
      setError('Start date must be before end date.');
      return;
    }
    setSaving(true);
    try {
      await saveTradeWindowSettings(leagueId, {
        trade_start_at: form.trade_start_at || null,
        trade_end_at: form.trade_end_at || null,
        timezone: form.timezone,
        is_active: form.is_active,
      });
      setMessage('Trade window settings saved.');
      load();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to save settings.');
    } finally {
      setSaving(false);
    }
  };

  const windowBanner = settings
    ? settings.is_active
      ? { cls: 'bg-green-500/10 border-green-400/30 text-green-300', label: 'Trade window is OPEN' }
      : { cls: 'bg-red-500/10 border-red-400/30 text-red-300', label: 'Trade window is CLOSED' }
    : null;

  return (
    <div className={cardSurface}>
      <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Trade Window Configuration</h2>

      {windowBanner && (
        <div className={`mb-4 rounded-lg border px-3 py-2 text-sm font-semibold ${windowBanner.cls}`}>
          {windowBanner.label}
          {settings?.trade_start_at && (
            <span className="ml-2 font-normal opacity-80">
              {fmtDt(settings.trade_start_at)} → {fmtDt(settings.trade_end_at) || 'no end set'}
            </span>
          )}
        </div>
      )}

      {loading && <LoadingState />}
      {!loading && error && (
        <div className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
          {error}
        </div>
      )}

      {!loading && !error && (
        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Trade Window Start
              </label>
              <input
                type="datetime-local"
                className={inputBase}
                value={form.trade_start_at}
                onChange={(e) => handleChange('trade_start_at', e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Trade Window End
              </label>
              <input
                type="datetime-local"
                className={inputBase}
                value={form.trade_end_at}
                onChange={(e) => handleChange('trade_end_at', e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Timezone
              </label>
              <select
                className={inputBase}
                value={form.timezone}
                onChange={(e) => handleChange('timezone', e.target.value)}
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-3 pt-5">
              <button
                type="button"
                role="switch"
                aria-checked={form.is_active}
                onClick={() => handleChange('is_active', !form.is_active)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500/40 ${form.is_active ? 'bg-cyan-600' : 'bg-slate-600'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${form.is_active ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
              <span className="text-sm text-slate-700 dark:text-slate-300">
                {form.is_active ? 'Window active (trades allowed)' : 'Window inactive (trades blocked)'}
              </span>
            </div>
          </div>

          {message && (
            <div className="rounded-lg border border-green-400/30 bg-green-500/10 px-3 py-2 text-sm text-green-300">
              {message}
            </div>
          )}
          {error && (
            <div className="rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}

          <div className="flex justify-end">
            <button type="submit" className={buttonPrimary} disabled={saving}>
              {saving ? 'Saving…' : 'Save Trade Window'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

// ── Trade Detail Drawer ───────────────────────────────────────────────────────

function TradeDetailDrawer({ leagueId, tradeId, onClose, onAction }) {
  const [detail, setDetail] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [comments, setComments] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [acting, setActing] = useState(false);

  useEffect(() => {
    if (!tradeId) return;
    setLoading(true);
    Promise.all([
      fetchTradeDetail(leagueId, tradeId).catch(() => null),
      fetchTradeHistory(leagueId, tradeId).catch(() => []),
    ]).then(([d, h]) => {
      setDetail(d);
      setHistory(Array.isArray(h) ? h : []);
      setLoading(false);
    });
  }, [leagueId, tradeId]);

  const handleAction = async (action) => {
    setActionMsg('');
    setActing(true);
    try {
      if (action === 'approve') {
        await approveTrade(leagueId, tradeId, comments);
      } else {
        await rejectTrade(leagueId, tradeId, comments);
      }
      onAction(tradeId, action);
      onClose();
    } catch (err) {
      const d = err?.response?.data?.detail;
      setActionMsg(typeof d === 'string' ? d : `Failed to ${action} trade.`);
    } finally {
      setActing(false);
    }
  };

  return (
    <>
      <div className={`fixed inset-0 bg-black/50 ${layerBackdrop}`} onClick={onClose} aria-hidden="true" />
      <div
        className={`fixed right-0 top-0 h-full w-full max-w-lg overflow-y-auto bg-white dark:bg-slate-900 shadow-2xl ${layerModal} flex flex-col`}
        role="dialog"
        aria-modal="true"
        aria-label="Trade Detail"
      >
        <div className="flex items-center justify-between border-b border-slate-300 dark:border-slate-800 px-4 py-3">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">Trade Detail</h2>
          <button type="button" onClick={onClose} className={buttonSecondary} aria-label="Close drawer">
            <FiX />
          </button>
        </div>

        <div className="flex-1 p-4 space-y-5">
          {loading && <LoadingState />}
          {!loading && !detail && <EmptyState message="Trade details unavailable." />}

          {!loading && detail && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1">Team A</p>
                  <p className="text-sm font-medium text-slate-900 dark:text-white">{detail.team_a_name || `Team ${detail.team_a_id}`}</p>
                  <p className={`text-xs mt-1 ${textMuted}`}>Offers: {summarizeAssets(detail.assets_from_a)}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1">Team B</p>
                  <p className="text-sm font-medium text-slate-900 dark:text-white">{detail.team_b_name || `Team ${detail.team_b_id}`}</p>
                  <p className={`text-xs mt-1 ${textMuted}`}>Offers: {summarizeAssets(detail.assets_from_b)}</p>
                </div>
              </div>

              {[{ label: 'Assets from Team A', items: detail.assets_from_a }, { label: 'Assets from Team B', items: detail.assets_from_b }].map(({ label, items }) => (
                <div key={label}>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">{label}</p>
                  <ul className="space-y-1">
                    {(items || []).map((a, i) => (
                      <li key={i} className="text-sm text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 rounded px-2 py-1">
                        {a.asset_type === 'PLAYER' && (a.player_name || `Player #${a.player_id}`)}
                        {a.asset_type === 'DRAFT_PICK' && `Pick #${a.draft_pick_id}${a.season_year ? ` (${a.season_year})` : ''}`}
                        {a.asset_type === 'DRAFT_DOLLARS' && `$${Number(a.amount || 0)} draft dollars`}
                      </li>
                    ))}
                    {(!items || items.length === 0) && <li className={`text-sm ${textMuted}`}>None</li>}
                  </ul>
                </div>
              ))}

              {history.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">Audit History</p>
                  <ul className="space-y-1">
                    {history.map((ev, i) => (
                      <li key={i} className="text-xs text-slate-600 dark:text-slate-400 flex items-start gap-2 flex-wrap">
                        <span className="font-semibold text-slate-700 dark:text-slate-300">{ev.event_type}</span>
                        {ev.commissioner_comments && <span className="italic">"{ev.commissioner_comments}"</span>}
                        <span className="ml-auto shrink-0">{fmtDt(ev.created_at)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  Commissioner Comment (optional)
                </label>
                <textarea
                  rows={3}
                  className={inputBase}
                  placeholder="Add a comment visible in the trade history…"
                  value={comments}
                  onChange={(e) => setComments(e.target.value)}
                />
              </div>

              {actionMsg && (
                <div className="rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                  {actionMsg}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  type="button"
                  className={`${buttonPrimary} flex items-center gap-2`}
                  disabled={acting}
                  onClick={() => handleAction('approve')}
                >
                  <FiCheck /> {acting ? 'Processing…' : 'Approve Trade'}
                </button>
                <button
                  type="button"
                  className={`${buttonDanger} flex items-center gap-2`}
                  disabled={acting}
                  onClick={() => handleAction('reject')}
                >
                  <FiXCircle /> {acting ? 'Processing…' : 'Reject Trade'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ManageTrades() {
  const leagueId = useActiveLeague();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [selectedTradeId, setSelectedTradeId] = useState(null);

  const loadTrades = useCallback(async () => {
    if (!leagueId) {
      setTrades([]);
      setLoading(false);
      setMessage('No active league selected.');
      return;
    }
    setLoading(true);
    setMessage('');
    try {
      setTrades(await fetchPendingTrades(leagueId));
    } catch {
      setTrades([]);
      setMessage('Failed to load pending trades.');
    } finally {
      setLoading(false);
    }
  }, [leagueId]);

  useEffect(() => { loadTrades(); }, [loadTrades]);

  const handleAction = (tradeId, action) => {
    setTrades((prev) => prev.filter((t) => t.id !== tradeId));
    setMessage(`Trade ${action === 'approve' ? 'approved' : 'rejected'} successfully.`);
  };

  return (
    <PageTemplate
      title="Manage Trades"
      subtitle="Configure the trade window and review pending trades."
      actions={
        <Link to="/commissioner" className={`${buttonSecondary} gap-2 px-3 py-2 text-sm no-underline`}>
          <FiChevronLeft /> Back
        </Link>
      }
    >
      {/* Trade window config + open/closed status banner */}
      <TradeWindowSettings leagueId={leagueId} />

      {/* Pending queue */}
      <div className={cardSurface}>
        <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Pending Trades</h2>

        {message && (
          <div className="mb-4 rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-300">
            {message}
          </div>
        )}

        {loading ? (
          <LoadingState />
        ) : !trades.length ? (
          <EmptyState message="No pending trades." />
        ) : (
          <StandardTableContainer>
            <StandardTable>
              <StandardTableHead
                headers={[
                  { key: 'teamA', label: 'Team A' },
                  { key: 'teamB', label: 'Team B' },
                  { key: 'offersA', label: 'Offers (A)' },
                  { key: 'offersB', label: 'Offers (B)' },
                  { key: 'actions', label: 'Actions' },
                ]}
              />
              <tbody>
                {trades.map((trade) => (
                  <StandardTableRow key={trade.id}>
                    <td className={tableCell}>{trade.team_a_name || 'Team A'}</td>
                    <td className={tableCell}>{trade.team_b_name || 'Team B'}</td>
                    <td className={tableCell}>{summarizeAssets(trade.assets_from_a)}</td>
                    <td className={tableCell}>{summarizeAssets(trade.assets_from_b)}</td>
                    <td className={tableCell}>
                      <button
                        type="button"
                        className={buttonSecondary}
                        onClick={() => setSelectedTradeId(trade.id)}
                      >
                        Review
                      </button>
                    </td>
                  </StandardTableRow>
                ))}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        )}
      </div>

      {/* Detail drawer */}
      {selectedTradeId && (
        <TradeDetailDrawer
          leagueId={leagueId}
          tradeId={selectedTradeId}
          onClose={() => setSelectedTradeId(null)}
          onAction={handleAction}
        />
      )}
    </PageTemplate>
  );
}
