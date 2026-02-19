import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';

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
      } catch (err) {
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
    } catch (err) {
      setMessage(`Failed to ${action} trade`);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto text-white min-h-screen">
      <h1 className="text-3xl font-black mb-6">Manage Trades</h1>
      <p className="mb-4 text-slate-400">View and manage player trades.</p>
      {message && <div className="mb-4 text-blue-300">{message}</div>}
      <div className="bg-slate-900 p-6 rounded-xl shadow">
        <h2 className="text-xl font-bold mb-4">Pending Trades</h2>
        {loading ? (
          <div>Loading...</div>
        ) : trades.length === 0 ? (
          <div className="text-slate-400">No pending trades.</div>
        ) : (
          <table className="w-full text-left border-separate border-spacing-y-2">
            <thead>
              <tr className="text-slate-400 text-sm">
                <th>From</th>
                <th>To</th>
                <th>Players</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
                <tr key={trade.id} className="bg-slate-800 hover:bg-slate-700">
                  <td>{trade.from_team || trade.from_user}</td>
                  <td>{trade.to_team || trade.to_user}</td>
                  <td>
                    {trade.players && trade.players.length > 0
                      ? trade.players.map((p) => p.name).join(', ')
                      : 'N/A'}
                  </td>
                  <td>
                    <button
                      className="bg-green-600 hover:bg-green-500 text-white font-bold py-1 px-4 rounded mr-2"
                      onClick={() => handleAction(trade.id, 'approve')}
                    >
                      Approve
                    </button>
                    <button
                      className="bg-red-600 hover:bg-red-500 text-white font-bold py-1 px-4 rounded"
                      onClick={() => handleAction(trade.id, 'deny')}
                    >
                      Deny
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
// ...existing code...
