import React from 'react';
import BracketAccordion from '../home/components/BracketAccordion';
import apiClient from '@api/client';
import PageTemplate from '@components/layout/PageTemplate';
import { Link } from 'react-router-dom';
import {
  buttonSecondary,
  cardSurface,
} from '@utils/uiStandards';

/* ignore-breakpoints */

export default function PlayoffBracket({ username, leagueId, setSubHeader }) {
  const [leagueName, setLeagueName] = React.useState('');

  // fetch league name for display
  React.useEffect(() => {
    if (leagueId) {
      apiClient
        .get(`/leagues/${leagueId}`)
        .then((res) => setLeagueName(res.data.name || ''))
        .catch(() => setLeagueName(''));
    }
  }, [leagueId]);

  // update sub-header with user/league info and page title
  React.useEffect(() => {
    if (setSubHeader) {
      const parts = [];
      if (username) parts.push(username);
      if (leagueName) parts.push(leagueName);
      parts.push('Playoff Bracket');
      setSubHeader(parts.join(' \u2014 ')); // em dash separation
    }
    return () => {
      if (setSubHeader) setSubHeader('');
    };
  }, [username, leagueName, setSubHeader]);

  return (
    <PageTemplate
      title="Playoff Bracket"
      subtitle="View playoff seeding and matchup progression."
    >
      <div className="mb-3 rounded-lg border border-slate-700 bg-slate-900/40 p-3">
        <p className="text-xs text-slate-300">
          Historical bracket lookup has moved to League History.
        </p>
        <Link to="/league-history/season-records" className={`${buttonSecondary} mt-2 inline-flex`}>
          Open Historical Brackets
        </Link>
      </div>
      <div className={cardSurface}>
        <BracketAccordion leagueId={leagueId} showHistoricalToggle={false} />
      </div>
    </PageTemplate>
  );
}
