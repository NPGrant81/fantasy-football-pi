import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '@api/client';
import {
  buttonPrimary,
  cardSurface,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '@utils/uiStandards';

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
      <div className={`${pageShell} text-center text-slate-600 dark:text-slate-400`}>
        Loading waiver rules...
      </div>
    );
  }

  return (
    <div className={pageShell}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Waiver Wire Rules</h1>
        <p className={pageSubtitle}>Current waiver deadlines, budgets, and tie-break settings.</p>
      </div>

      <div className={`${cardSurface} space-y-4 text-slate-700 dark:text-slate-300`}>
        <div>
          <strong>Waiver Deadline:</strong> {rules.waiver_deadline || 'Not set'}
        </div>
        <div>
          <strong>Starting FAAB Budget:</strong>{' '}
          {rules.starting_waiver_budget ?? 'N/A'}
        </div>
        <div>
          <strong>Waiver System:</strong> {rules.waiver_system || 'N/A'}
        </div>
        <div>
          <strong>Tie-breaker:</strong> {rules.waiver_tiebreaker || 'N/A'}
        </div>
        <div>
          <strong>Roster Size Limit:</strong> {rules.roster_size || 'Default'}
        </div>
      </div>

      {userInfo.is_commissioner && (
        <div>
          <button
            className={buttonPrimary}
            onClick={() => navigate('/commissioner/manage-waiver-rules')}
          >
            Edit Waiver Rules
          </button>
        </div>
      )}
    </div>
  );
}
