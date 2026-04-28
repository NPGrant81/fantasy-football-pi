/* ignore-breakpoints: this modal's layout and responsiveness are handled by shared uiStandards modal classes; no additional breakpoint-specific behaviour is required */
import React, { useEffect, useState } from 'react';
import { FiShield } from 'react-icons/fi';
import apiClient from '@api/client';
import { useActiveLeague } from '@context/LeagueContext';
import {
  buttonPrimary,
  buttonSecondary,
  inputBase,
  modalCloseButton,
  modalDescription,
  modalOverlay,
  modalSurface,
  modalTitle,
  textMeta,
} from '@utils/uiStandards';

const BOOL_OPTIONS = [
  { value: 'true', label: 'Yes' },
  { value: 'false', label: 'No' },
];

function BoolSelect({ value, onChange, id }) {
  return (
    <select
      id={id}
      className={inputBase}
      value={String(value)}
      onChange={(e) => onChange(e.target.value === 'true')}
    >
      {BOOL_OPTIONS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function NumberInput({ value, onChange, id, min = 1, max, placeholder }) {
  return (
    <input
      id={id}
      type="number"
      className={inputBase}
      value={value ?? ''}
      min={min}
      max={max}
      placeholder={placeholder}
      onChange={(e) => {
        const v = e.target.value;
        const n = Number(v);
        onChange(v === '' ? null : (Number.isFinite(n) ? Math.trunc(n) : null));
      }}
    />
  );
}

export default function TradeRulesModal({ open, onClose }) {
  const leagueId = useActiveLeague();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [rules, setRules] = useState({
    trade_deadline: '',
    allow_playoff_trades: true,
    require_commissioner_approval: true,
    trade_veto_enabled: false,
    trade_veto_threshold: null,
    trade_review_period_hours: null,
    trade_max_players_per_side: null,
    trade_league_vote_enabled: false,
    trade_league_vote_threshold: null,
  });

  useEffect(() => {
    if (!open || !leagueId) return;
    setLoading(true);
    setMessage('');
    apiClient
      .get(`/leagues/${leagueId}/trade-rules`)
      .then((res) => setRules(res.data))
      .catch(() => setMessage('Failed to load trade rules.'))
      .finally(() => setLoading(false));
  }, [open, leagueId]);

  const handleSave = async () => {
    if (!leagueId) return;
    setSaving(true);
    setMessage('');
    try {
      await apiClient.put(`/leagues/${leagueId}/trade-rules`, rules);
      setMessage('Trade rules saved.');
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Failed to save trade rules.');
    } finally {
      setSaving(false);
    }
  };

  const set = (field) => (value) => setRules((prev) => ({ ...prev, [field]: value }));

  if (!open) return null;
  return (
    <div className={modalOverlay}>
      <div className={`${modalSurface} max-w-2xl`}>
        <button onClick={onClose} className={modalCloseButton} aria-label="Close">
          ✕
        </button>
        <h2 className={modalTitle}>
          <FiShield className="inline mr-2" />
          Trade Rules
        </h2>
        <p className={modalDescription}>
          Configure trade governance, review periods, veto logic, and player limits.
        </p>

        {loading ? (
          <div className="py-6 text-center text-sm text-slate-400">Loading…</div>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2">

            {/* Trade Deadline */}
            <div>
              <label htmlFor="trade_deadline" className={`block mb-1 font-semibold ${textMeta}`}>
                Trade Deadline
              </label>
              <input
                id="trade_deadline"
                type="datetime-local"
                className={inputBase}
                value={rules.trade_deadline
                  ? rules.trade_deadline.replace('Z', '').replace(/\+\d{2}:\d{2}$/, '').substring(0, 16)
                  : ''}
                onChange={(e) => {
                  const v = e.target.value;
                  set('trade_deadline')(v ? v + ':00Z' : null);
                }}
              />
            </div>

            {/* Allow Playoff Trades */}
            <div>
              <label htmlFor="allow_playoff_trades" className={`block mb-1 font-semibold ${textMeta}`}>
                Allow Playoff Trades
              </label>
              <BoolSelect
                id="allow_playoff_trades"
                value={rules.allow_playoff_trades}
                onChange={set('allow_playoff_trades')}
              />
            </div>

            {/* Max Players Per Side */}
            <div>
              <label htmlFor="trade_max_players_per_side" className={`block mb-1 font-semibold ${textMeta}`}>
                Max Players Per Side
              </label>
              <NumberInput
                id="trade_max_players_per_side"
                value={rules.trade_max_players_per_side}
                onChange={set('trade_max_players_per_side')}
                placeholder="No limit"
                max={20}
              />
            </div>

            {/* Review Period */}
            <div>
              <label htmlFor="trade_review_period_hours" className={`block mb-1 font-semibold ${textMeta}`}>
                Review Period (hours)
              </label>
              <NumberInput
                id="trade_review_period_hours"
                value={rules.trade_review_period_hours}
                onChange={set('trade_review_period_hours')}
                placeholder="No review period"
                max={168}
              />
            </div>

            {/* Require Commissioner Approval */}
            <div>
              <label htmlFor="require_commissioner_approval" className={`block mb-1 font-semibold ${textMeta}`}>
                Require Commissioner Approval
              </label>
              <BoolSelect
                id="require_commissioner_approval"
                value={rules.require_commissioner_approval}
                onChange={set('require_commissioner_approval')}
              />
            </div>

            {/* Veto Enabled */}
            <div>
              <label htmlFor="trade_veto_enabled" className={`block mb-1 font-semibold ${textMeta}`}>
                Owner Veto Allowed
              </label>
              <BoolSelect
                id="trade_veto_enabled"
                value={rules.trade_veto_enabled}
                onChange={set('trade_veto_enabled')}
              />
            </div>

            {/* Veto Threshold */}
            {rules.trade_veto_enabled && (
              <div>
                <label htmlFor="trade_veto_threshold" className={`block mb-1 font-semibold ${textMeta}`}>
                  Veto Threshold (# of owners)
                </label>
                <NumberInput
                  id="trade_veto_threshold"
                  value={rules.trade_veto_threshold}
                  onChange={set('trade_veto_threshold')}
                  placeholder="e.g. 4"
                  max={20}
                />
              </div>
            )}

            {/* League Vote Enabled */}
            <div>
              <label htmlFor="trade_league_vote_enabled" className={`block mb-1 font-semibold ${textMeta}`}>
                League Vote Required
              </label>
              <BoolSelect
                id="trade_league_vote_enabled"
                value={rules.trade_league_vote_enabled}
                onChange={set('trade_league_vote_enabled')}
              />
            </div>

            {/* League Vote Threshold */}
            {rules.trade_league_vote_enabled && (
              <div>
                <label htmlFor="trade_league_vote_threshold" className={`block mb-1 font-semibold ${textMeta}`}>
                  Approval Threshold (% of owners)
                </label>
                <NumberInput
                  id="trade_league_vote_threshold"
                  value={rules.trade_league_vote_threshold}
                  onChange={set('trade_league_vote_threshold')}
                  placeholder="e.g. 51"
                  max={100}
                />
              </div>
            )}

          </div>
        )}

        {message && (
          <p className={`mt-4 text-sm ${message.includes('saved') ? 'text-green-400' : 'text-red-400'}`}>
            {message}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} className={buttonSecondary}>
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={loading || saving}
            className={buttonPrimary}
          >
            {saving ? 'Saving…' : 'Save Rules'}
          </button>
        </div>
      </div>
    </div>
  );
}

