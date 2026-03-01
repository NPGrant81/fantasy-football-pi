import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';
import {
  buttonDanger,
  buttonPrimary,
  cardSurface,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
  tableHead,
  tableSurface,
} from '@utils/uiStandards';

/* ignore-breakpoints */

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
        setTrades(res.data);
      } catch {
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
      setTrades(trades.filter((t) => t.id !== tradeId));
      setMessage(`Trade ${action}d successfully!`);
    } catch {
      setMessage(`Failed to ${action} trade`);
    }
  };

  return (
    <div className={pageShell}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Manage Trades</h1>
        <p className={pageSubtitle}>View and review pending trades.</p>
      </div>

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
          <div className="text-slate-600 dark:text-slate-400">Loading...</div>
        ) : trades.length === 0 ? (
          <div className="text-slate-600 dark:text-slate-400">
            No pending trades.
          </div>
        ) : (
          <div className={tableSurface}>
            <table className="w-full text-left text-sm text-slate-700 dark:text-slate-300">
              <thead className={tableHead}>
                <tr>
                  <th>From</th>
                  <th>To</th>
                  <th>Players</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade) => (
                  <tr
                    key={trade.id}
                    className="border-t border-slate-300 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800/40"
                  >
                    <td className="px-3 py-2">
                      {trade.from_team || trade.from_user}
                    </td>
                    <td className="px-3 py-2">
                      {trade.to_team || trade.to_user}
                    </td>
                    <td>
                      {trade.players && trade.players.length > 0
                        ? trade.players.map((p) => p.name).join(', ')
                        : 'N/A'}
                    </td>
                    <td className="px-3 py-2 space-x-2">
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
// ...existing code...
