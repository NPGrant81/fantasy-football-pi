import React, { useState, useEffect } from 'react';
import apiClient from '@api/client';

// Simple table-based leaderboard showing manager efficiency
const ManagerEfficiencyLeaderboard = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const userRes = await apiClient.get('/auth/me');
        const leagueId = userRes.data?.league_id;
        if (!leagueId) {
          setError('League not found');
          setLoading(false);
          return;
        }
        const res = await apiClient.get(
          `/analytics/league/${leagueId}/leaderboard`
        );
        setRows(res.data || []);
      } catch (err) {
        console.error(err);
        setError(err.message || 'Failed to load leaderboard');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return <p>Loading leaderboard...</p>;
  }
  if (error) {
    return <p className="text-red-500">Error: {error}</p>;
  }

  if (rows.length === 0) {
    return <p>No efficiency data available.</p>;
  }

  return (
    <div className="md:p-6" style={{ padding: '20px' }}>
      <h3 className="text-white text-lg font-bold mb-4">
        Efficiency Leaderboard
      </h3>
      <table className="w-full text-sm table-auto">
        <thead>
          <tr className="bg-gray-700">
            <th className="px-2 py-1 text-left">Rank</th>
            <th className="px-2 py-1 text-left">Manager ID</th>
            <th className="px-2 py-1 text-left">Efficiency</th>
            <th className="px-2 py-1 text-left">Personality</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => (
            <tr
              key={r.manager_id}
              className={idx % 2 === 0 ? 'bg-gray-800' : 'bg-gray-900'}
            >
              <td className="px-2 py-1">{idx + 1}</td>
              <td className="px-2 py-1">{r.manager_id}</td>
              <td className="px-2 py-1">{r.efficiency_display}</td>
              <td className="px-2 py-1">{r.personality}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ManagerEfficiencyLeaderboard;
