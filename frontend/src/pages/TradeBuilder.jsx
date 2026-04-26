import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { FiChevronLeft, FiPlus, FiTrash2 } from 'react-icons/fi';
import { useActiveLeague } from '@context/LeagueContext';
import PageTemplate from '@components/layout/PageTemplate';
import { LoadingState, EmptyState } from '@components/common/AsyncState';
import {
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  inputBase,
  textMuted,
} from '@utils/uiStandards';
import { fetchLeagueTeams, fetchTeamRoster, submitTrade } from '@api/tradesApi';

/* ignore-breakpoints */

const ASSET_TYPES = ['PLAYER', 'DRAFT_PICK', 'DRAFT_DOLLARS'];

// ── Helpers ──────────────────────────────────────────────────────────────────

function assetLabel(a) {
  if (a.asset_type === 'PLAYER') return a.player_name || `Player #${a.player_id}`;
  if (a.asset_type === 'DRAFT_PICK') return `Pick #${a.draft_pick_id}${a.season_year ? ` (${a.season_year})` : ''}`;
  if (a.asset_type === 'DRAFT_DOLLARS') return `$${Number(a.amount || 0)} draft dollars`;
  return a.asset_type;
}

// ── Asset Picker ─────────────────────────────────────────────────────────────

function AssetRow({ asset, roster, onRemove, onChange }) {
  const players = roster.filter((p) => p.player_id || p.id);

  return (
    <div className="flex items-start gap-2 p-2 bg-slate-100 dark:bg-slate-800 rounded-lg">
      {/* Asset type selector */}
      <select
        className="rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/40 min-w-[130px]"
        value={asset.asset_type}
        onChange={(e) => onChange({ ...asset, asset_type: e.target.value, player_id: null, draft_pick_id: null, amount: '' })}
      >
        {ASSET_TYPES.map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
      </select>

      {/* Dynamic fields per type */}
      {asset.asset_type === 'PLAYER' && (
        <select
          className="flex-1 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
          value={asset.player_id || ''}
          onChange={(e) => onChange({ ...asset, player_id: e.target.value ? Number(e.target.value) : null })}
        >
          <option value="">— select player —</option>
          {players.map((p) => (
            <option key={p.player_id || p.id} value={p.player_id || p.id}>
              {p.player_name || p.name || `Player #${p.player_id || p.id}`}
            </option>
          ))}
        </select>
      )}

      {asset.asset_type === 'DRAFT_PICK' && (
        <div className="flex gap-2 flex-1">
          <input
            type="number"
            placeholder="Pick ID"
            className="flex-1 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
            value={asset.draft_pick_id || ''}
            min="1"
            onChange={(e) => onChange({ ...asset, draft_pick_id: e.target.value ? Number(e.target.value) : null })}
          />
          <input
            type="number"
            placeholder="Year"
            className="w-24 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
            value={asset.season_year || ''}
            min="2020"
            max="2040"
            onChange={(e) => onChange({ ...asset, season_year: e.target.value ? Number(e.target.value) : null })}
          />
        </div>
      )}

      {asset.asset_type === 'DRAFT_DOLLARS' && (
        <div className="flex items-center gap-1 flex-1">
          <span className="text-sm text-slate-500 dark:text-slate-400">$</span>
          <input
            type="number"
            placeholder="Amount"
            className="flex-1 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-1.5 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
            value={asset.amount || ''}
            min="1"
            onChange={(e) => onChange({ ...asset, amount: e.target.value ? Number(e.target.value) : '' })}
          />
        </div>
      )}

      <button
        type="button"
        onClick={onRemove}
        className="mt-1 text-red-500 hover:text-red-400 focus:outline-none"
        aria-label="Remove asset"
      >
        <FiTrash2 size={16} />
      </button>
    </div>
  );
}

// ── Asset Panel (one side of the trade) ──────────────────────────────────────

function AssetPanel({ title, teamId, roster, assets, onAddAsset, onRemoveAsset, onChangeAsset }) {
  return (
    <div className={cardSurface}>
      <h3 className="text-base font-bold text-slate-900 dark:text-white mb-3">{title}</h3>
      <div className="space-y-2">
        {assets.map((a, i) => (
          <AssetRow
            key={i}
            asset={a}
            roster={roster}
            onRemove={() => onRemoveAsset(i)}
            onChange={(updated) => onChangeAsset(i, updated)}
          />
        ))}
        {assets.length === 0 && (
          <p className={`text-sm ${textMuted}`}>No assets added yet.</p>
        )}
      </div>
      <button
        type="button"
        onClick={onAddAsset}
        className={`mt-3 ${buttonSecondary} flex items-center gap-2 text-sm`}
        disabled={!teamId}
      >
        <FiPlus size={14} /> Add Asset
      </button>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const newAsset = () => ({ asset_type: 'PLAYER', player_id: null, draft_pick_id: null, season_year: null, amount: '' });

export default function TradeBuilder() {
  const leagueId = useActiveLeague();

  const [teams, setTeams] = useState([]);
  const [teamsLoading, setTeamsLoading] = useState(true);

  const [teamBId, setTeamBId] = useState('');
  const [rosterB, setRosterB] = useState([]);
  const [rosterBLoading, setRosterBLoading] = useState(false);

  // My roster (team A) loaded from /auth/me → team context
  const myTeamId = localStorage.getItem('team_id') || localStorage.getItem('owner_id') || null;
  const [rosterA, setRosterA] = useState([]);

  const [assetsFromA, setAssetsFromA] = useState([]);
  const [assetsFromB, setAssetsFromB] = useState([]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Load teams
  useEffect(() => {
    if (!leagueId) return;
    setTeamsLoading(true);
    fetchLeagueTeams(leagueId)
      .then(setTeams)
      .catch(() => setTeams([]))
      .finally(() => setTeamsLoading(false));
  }, [leagueId]);

  // Load my roster
  useEffect(() => {
    if (!leagueId || !myTeamId) return;
    fetchTeamRoster(leagueId, myTeamId).catch(() => []).then(setRosterA);
  }, [leagueId, myTeamId]);

  // Load team B roster when opponent selected
  const loadRosterB = useCallback(async (tid) => {
    if (!tid || !leagueId) { setRosterB([]); return; }
    setRosterBLoading(true);
    try {
      setRosterB(await fetchTeamRoster(leagueId, tid));
    } catch {
      setRosterB([]);
    } finally {
      setRosterBLoading(false);
    }
  }, [leagueId]);

  const handleTeamBChange = (tid) => {
    setTeamBId(tid);
    setAssetsFromB([]);
    loadRosterB(tid);
    setError('');
  };

  // Asset mutations — side A
  const addA = () => setAssetsFromA((p) => [...p, newAsset()]);
  const removeA = (i) => setAssetsFromA((p) => p.filter((_, idx) => idx !== i));
  const changeA = (i, v) => setAssetsFromA((p) => p.map((a, idx) => idx === i ? v : a));

  // Asset mutations — side B
  const addB = () => setAssetsFromB((p) => [...p, newAsset()]);
  const removeB = (i) => setAssetsFromB((p) => p.filter((_, idx) => idx !== i));
  const changeB = (i, v) => setAssetsFromB((p) => p.map((a, idx) => idx === i ? v : a));

  const validate = () => {
    if (!leagueId) return 'No active league selected.';
    if (!teamBId) return 'Please select a trade partner.';
    if (assetsFromA.length === 0 && assetsFromB.length === 0) return 'Add at least one asset to the trade.';
    for (const a of assetsFromA) {
      if (a.asset_type === 'PLAYER' && !a.player_id) return 'Select a player for all your player assets.';
      if (a.asset_type === 'DRAFT_PICK' && !a.draft_pick_id) return 'Enter a pick ID for all draft pick assets.';
      if (a.asset_type === 'DRAFT_DOLLARS' && !a.amount) return 'Enter an amount for all draft dollar assets.';
    }
    for (const a of assetsFromB) {
      if (a.asset_type === 'PLAYER' && !a.player_id) return 'Select a player for all opponent player assets.';
      if (a.asset_type === 'DRAFT_PICK' && !a.draft_pick_id) return 'Enter a pick ID for all opponent draft pick assets.';
      if (a.asset_type === 'DRAFT_DOLLARS' && !a.amount) return 'Enter an amount for all opponent draft dollar assets.';
    }
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    const validationError = validate();
    if (validationError) { setError(validationError); return; }

    setSubmitting(true);
    try {
      const buildAsset = (a) => {
        const base = { asset_type: a.asset_type };
        if (a.asset_type === 'PLAYER') return { ...base, player_id: a.player_id };
        if (a.asset_type === 'DRAFT_PICK') return { ...base, draft_pick_id: a.draft_pick_id, season_year: a.season_year || null };
        if (a.asset_type === 'DRAFT_DOLLARS') return { ...base, amount: Number(a.amount) };
        return base;
      };
      await submitTrade(leagueId, {
        team_b_id: Number(teamBId),
        assets_from_a: assetsFromA.map(buildAsset),
        assets_from_b: assetsFromB.map(buildAsset),
      });
      setSuccess('Trade submitted! It is now pending commissioner review.');
      setAssetsFromA([]);
      setAssetsFromB([]);
      setTeamBId('');
      setRosterB([]);
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === 'string' ? d : 'Failed to submit trade. Check your assets and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PageTemplate
      title="Trade Builder"
      subtitle="Propose a trade with another team. Your commissioner will review it."
      actions={
        <Link to="/team" className={`${buttonSecondary} gap-2 px-3 py-2 text-sm no-underline`}>
          <FiChevronLeft /> Back
        </Link>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Trade partner selector */}
        <div className={cardSurface}>
          <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Trade Partner</h2>
          {teamsLoading ? (
            <LoadingState />
          ) : teams.length === 0 ? (
            <EmptyState message="No teams found in this league." />
          ) : (
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Select opponent team
              </label>
              <select
                className={`${inputBase} max-w-xs`}
                value={teamBId}
                onChange={(e) => handleTeamBChange(e.target.value)}
              >
                <option value="">— choose a team —</option>
                {teams
                  .filter((t) => String(t.owner_id || t.id) !== String(myTeamId))
                  .map((t) => (
                    <option key={t.owner_id || t.id} value={t.owner_id || t.id}>
                      {t.team_name || t.owner_name || `Team #${t.owner_id || t.id}`}
                    </option>
                  ))}
              </select>
            </div>
          )}
        </div>

        {/* Asset panels */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              You give (Team A)
            </p>
            <AssetPanel
              title="Your Assets"
              teamId={myTeamId}
              roster={rosterA}
              assets={assetsFromA}
              onAddAsset={addA}
              onRemoveAsset={removeA}
              onChangeAsset={changeA}
            />
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              You receive (Team B)
            </p>
            {rosterBLoading ? (
              <LoadingState />
            ) : (
              <AssetPanel
                title="Their Assets"
                teamId={teamBId}
                roster={rosterB}
                assets={assetsFromB}
                onAddAsset={addB}
                onRemoveAsset={removeB}
                onChangeAsset={changeB}
              />
            )}
          </div>
        </div>

        {/* Trade summary */}
        {(assetsFromA.length > 0 || assetsFromB.length > 0) && (
          <div className={cardSurface}>
            <h3 className="text-base font-bold text-slate-900 dark:text-white mb-3">Trade Summary</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1">You Give</p>
                {assetsFromA.length === 0 ? (
                  <p className={`text-sm ${textMuted}`}>Nothing</p>
                ) : (
                  <ul className="space-y-0.5">
                    {assetsFromA.map((a, i) => <li key={i} className="text-sm text-slate-700 dark:text-slate-300">{assetLabel(a)}</li>)}
                  </ul>
                )}
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1">You Receive</p>
                {assetsFromB.length === 0 ? (
                  <p className={`text-sm ${textMuted}`}>Nothing</p>
                ) : (
                  <ul className="space-y-0.5">
                    {assetsFromB.map((a, i) => <li key={i} className="text-sm text-slate-700 dark:text-slate-300">{assetLabel(a)}</li>)}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Feedback */}
        {error && (
          <div className="rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-lg border border-green-400/30 bg-green-500/10 px-3 py-2 text-sm text-green-300">
            {success}
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            className={buttonPrimary}
            disabled={submitting || !teamBId}
          >
            {submitting ? 'Submitting…' : 'Submit Trade Proposal'}
          </button>
        </div>
      </form>
    </PageTemplate>
  );
}
