import React from 'react';
import BracketAccordion from '../home/components/BracketAccordion';
import apiClient from '@api/client';

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
    <div className="p-4">
      <h1 className="text-4xl font-black uppercase tracking-tighter mb-4">
        Playoff Bracket
      </h1>
      {/* main bracket accordion component contains season dropdown and match rendering */}
      <BracketAccordion leagueId={leagueId} />
    </div>
  );
}
