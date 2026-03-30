import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';
import { Link } from 'react-router-dom';
import { FiChevronLeft } from 'react-icons/fi';
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
  tableCell,
} from '@utils/uiStandards';

/* ignore-breakpoints */

const normalizeTrades = (payload) => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.trades)) return payload.trades;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
};

const summarizeAssets = (assets = []) => {
  if (!Array.isArray(assets) || assets.length === 0) return 'None';
  return assets
    .map((asset) => {
      if (asset.asset_type === 'PLAYER') {
        return asset.player_name || `Player #${asset.player_id}`;
      }
      if (asset.asset_type === 'DRAFT_PICK') {
        return `Pick #${asset.draft_pick_id}${asset.season_year ? ` (${asset.season_year})` : ''}`;
      }
      if (asset.asset_type === 'DRAFT_DOLLARS') {
        return `$${Number(asset.amount || 0)}`;
      }
      return asset.asset_type;
    })
    .join(', ');
};

export default function ManageTrades() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [leagueId, setLeagueId] = useState(null);
  const [actionComments, setActionComments] = useState({});

  const fetchTrades = async (currentLeagueId) => {
    if (!currentLeagueId) {
      setTrades([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setMessage('');
    try {
      const res = await apiClient.get(`/trades/leagues/${currentLeagueId}/pending-v2`);
      setTrades(normalizeTrades(res.data));
    } catch {
      setTrades([]);
      setMessage('Failed to load trades');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    async function bootstrap() {
      setLoading(true);
      setMessage('');
      try {
        const me = await apiClient.get('/auth/me');
        const resolvedLeagueId = Number(me.data?.league_id || 0) || null;
        setLeagueId(resolvedLeagueId);
        await fetchTrades(resolvedLeagueId);
      } catch {
        setTrades([]);
        setLeagueId(null);
        setMessage('Failed to load commissioner context');
        setLoading(false);
      }
    }
    bootstrap();
  }, []);

  const handleAction = async (tradeId, action) => {
    setMessage('');
    try {
      if (!leagueId) {
        setMessage('Unable to determine league context.');
        return;
      }
      const comments = actionComments[tradeId] || '';
      const endpoint =
        action === 'approve'
          ? `/trades/leagues/${leagueId}/${tradeId}/approve-v2`
          : `/trades/leagues/${leagueId}/${tradeId}/reject-v2`;
      await apiClient.post(endpoint, {
        commissioner_comments: comments,
      });
      setTrades((prevTrades) => prevTrades.filter((t) => t.id !== tradeId));
      setActionComments((prev) => {
        const next = { ...prev };
        delete next[tradeId];
        return next;
      });
      setMessage(`Trade ${action}d successfully!`);
    } catch {
      setMessage(`Failed to ${action} trade`);
    }
  };

  return (
    <PageTemplate
      title="Manage Trades"
      subtitle="View and review pending trades."
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
        <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-4">
          Pending Trades
        </h2>
        {loading ? (
          <LoadingState />
        ) : !Array.isArray(trades) || trades.length === 0 ? (
          <EmptyState message="No pending trades." />
        ) : (
          <StandardTableContainer>
            <StandardTable>
              <StandardTableHead
                headers={[
                  { key: 'from', label: 'From Team' },
                  { key: 'to', label: 'To Team' },
                  { key: 'assetsFromA', label: 'Assets From A' },
                  { key: 'assetsFromB', label: 'Assets From B' },
                  { key: 'comments', label: 'Comments' },
                  { key: 'actions', label: 'Actions' },
                ]}
              />
              <tbody>
                {trades.map((trade) => (
                  <StandardTableRow key={trade.id}>
                    <td className={tableCell}>{trade.team_a_name || 'Unknown Team A'}</td>
                    <td className={tableCell}>{trade.team_b_name || 'Unknown Team B'}</td>
                    <td className={tableCell}>
                      {summarizeAssets(trade.assets_from_a)}
                    </td>
                    <td className={tableCell}>
                      {summarizeAssets(trade.assets_from_b)}
                    </td>
                    <td className={tableCell}>
                      <textarea
                        rows={2}
                        className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                        placeholder="Optional commissioner comment"
                        value={actionComments[trade.id] || ''}
                        onChange={(e) =>
                          setActionComments((prev) => ({
                            ...prev,
                            [trade.id]: e.target.value,
                          }))
                        }
                      />
                    </td>
                    <td className={`${tableCell} space-x-2`}>
                      <button
                        type="button"
                        className={buttonPrimary}
                        onClick={() => handleAction(trade.id, 'approve')}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className={buttonDanger}
                        onClick={() => handleAction(trade.id, 'reject')}
                      >
                        Reject
                      </button>
                    </td>
                  </StandardTableRow>
                ))}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        )}
      </div>
    </PageTemplate>
  );
}
// ...existing code...
