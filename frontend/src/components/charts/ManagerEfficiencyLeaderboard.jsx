import React, { useState, useEffect } from 'react';
import { fetchCurrentUser } from '@api/commonApi';
import {
  fetchManagerEfficiencyLeaderboard,
  resolveRows,
} from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import { EmptyState, ErrorState, LoadingState } from '@components/common/AsyncState';

// Simple table-based leaderboard showing manager efficiency
const ManagerEfficiencyLeaderboard = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const user = await fetchCurrentUser();
        const leagueId = user?.league_id;
        if (!leagueId) {
          setError('League not found');
          setLoading(false);
          return;
        }
        const payload = await fetchManagerEfficiencyLeaderboard(leagueId);
        setRows(resolveRows(payload));
      } catch (err) {
        console.error(err);
        setError(normalizeApiError(err, 'Failed to load leaderboard'));
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return <LoadingState message="Loading leaderboard..." />;
  }
  if (error) {
    return <ErrorState message={error} />;
  }

  if (!Array.isArray(rows)) {
    console.warn('ManagerEfficiencyLeaderboard: rows is not an array', rows);
    return <EmptyState message="No efficiency data available." />;
  }
  if (rows.length === 0) {
    return <EmptyState message="No efficiency data available." />;
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
