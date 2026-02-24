import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '@api/client';

export default function WaiverRules({ leagueId }) {
  const [rules, setRules] = useState(null);
  const [userInfo, setUserInfo] = useState({ is_commissioner: false });
  const navigate = useNavigate();

  useEffect(() => {
    async function fetchData() {
      try {
        const userRes = await apiClient.get('/auth/me');
        setUserInfo({ is_commissioner: userRes.data.is_commissioner });
      } catch {}

      if (leagueId) {
        try {
          const res = await apiClient.get(`/leagues/${leagueId}/settings`);
          setRules(res.data);
        } catch {
          setRules({});
        }
      }
    }
    fetchData();
  }, [leagueId]);

  if (rules === null) {
    return (
      <div className="p-8 text-center text-slate-400">Loading waiver rules...</div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-8 text-white">
      <h1 className="text-4xl font-black mb-6">Waiver Wire Rules</h1>
      <div className="bg-slate-800 p-6 rounded-xl shadow space-y-4">
        <div>
          <strong>Waiver Deadline:</strong>{' '}
          {rules.waiver_deadline || 'Not set'}
        </div>
        <div>
          <strong>Roster Size Limit:</strong>{' '}
          {rules.roster_size || 'Default'}
        </div>
      </div>

      {userInfo.is_commissioner && (
        <div className="mt-6">
          <button
            className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-6 rounded"
            onClick={() => navigate('/commissioner/manage-waiver-rules')}
          >
            Edit Waiver Rules
          </button>
        </div>
      )}
    </div>
  );
}
