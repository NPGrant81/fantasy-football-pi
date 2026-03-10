/* ignore-breakpoints: page uses a fixed admin-style layout managed via uiStandards; responsive breakpoints are not required */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '@api/client';
import { LoadingState } from '@components/common/AsyncState';
import PageTemplate from '@components/layout/PageTemplate';
import {
  buttonPrimary,
  cardSurface,
  pageShell,
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
      <div className={pageShell}>
        <LoadingState message="Loading waiver rules..." />
      </div>
    );
  }

  return (
    <PageTemplate
      title="Waiver Wire Rules"
      subtitle="Current waiver deadlines, budgets, and tie-break settings."
    >

      <div
        className={`${cardSurface} space-y-4 text-slate-700 dark:text-slate-300`}
      >
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
    </PageTemplate>
  );
}
