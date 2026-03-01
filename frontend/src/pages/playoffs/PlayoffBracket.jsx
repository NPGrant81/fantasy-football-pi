import React from 'react';
import BracketAccordion from '../home/components/BracketAccordion';
import apiClient from '@api/client';
import {
  cardSurface,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
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
    <div className={pageShell}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Playoff Bracket</h1>
        <p className={pageSubtitle}>
          View playoff seeding and matchup progression.
        </p>
      </div>
      <div className={cardSurface}>
        <BracketAccordion leagueId={leagueId} />
      </div>
    </div>
  );
}
