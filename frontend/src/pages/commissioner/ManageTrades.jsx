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

export default function ManageTrades() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');

  useEffect(() => {
    async function fetchTrades() {
      setLoading(true);
      setMessage('');
      try {
        // Replace with real endpoint and league context as needed
        const res = await apiClient.get('/trades/pending');
        setTrades(normalizeTrades(res.data));
      } catch {
        setTrades([]);
        setMessage('Failed to load trades');
      } finally {
        setLoading(false);
      }
    }
    fetchTrades();
  }, []);

  const handleAction = async (tradeId, action) => {
    setMessage('');
    try {
      // Replace with real endpoint
      await apiClient.post(`/trades/${tradeId}/${action}`);
      setTrades((prevTrades) => prevTrades.filter((t) => t.id !== tradeId));
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
                  { key: 'from', label: 'From' },
                  { key: 'to', label: 'To' },
                  { key: 'players', label: 'Players' },
                  { key: 'actions', label: 'Actions' },
                ]}
              />
              <tbody>
                {trades.map((trade) => (
                  <StandardTableRow key={trade.id}>
                    <td className={tableCell}>{trade.from_team || trade.from_user}</td>
                    <td className={tableCell}>{trade.to_team || trade.to_user}</td>
                    <td className={tableCell}>
                      {trade.players && trade.players.length > 0
                        ? trade.players.map((p) => p.name).join(', ')
                        : 'N/A'}
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
                        onClick={() => handleAction(trade.id, 'deny')}
                      >
                        Deny
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
