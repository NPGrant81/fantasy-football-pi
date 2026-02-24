import React, { useState, useEffect } from 'react';
import apiClient from '@api/client';

export default function BracketAccordion() {
  const [open, setOpen] = useState(false);
  const [bracket, setBracket] = useState(null);
  const [loading, setLoading] = useState(false);
  const leagueId = localStorage.getItem('fantasyLeagueId');
  const season = new Date().getFullYear();

  useEffect(() => {
    if (open && leagueId) {
      setLoading(true);
      apiClient
        .get(`/playoffs/bracket?league_id=${leagueId}&season=${season}`)
        .then((res) => setBracket(res.data))
        .catch(() => setBracket(null))
        .finally(() => setLoading(false));
    }
  }, [open, leagueId, season]);

  const renderMatches = (matches) => {
    if (!matches) return null;
    return matches.map((m) => (
      <div
        key={m.match_id}
        className="border border-slate-700 rounded p-2 mb-2 bg-slate-900/30"
      >
        <div className="text-xs text-slate-400">{m.match_id}</div>
        {m.is_bye ? (
          <div className="text-sm text-yellow-400">BYE → seed {m.team_1_id}</div>
        ) : (
          <div className="text-sm flex justify-between">
            <span>#{m.team_1_id || 'TBD'}</span>
            <span>vs</span>
            <span>#{m.team_2_id || 'TBD'}</span>
          </div>
        )}
      </div>
    ));
  };

  return (
    <details
      className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 shadow-xl"
      onToggle={(e) => setOpen(e.target.open)}
    >
      <summary className="cursor-pointer text-lg font-bold text-white">
        Playoff Bracket
      </summary>

      {loading && <div className="text-slate-400 mt-2">Loading...</div>}
      {!loading && bracket && (
        <div className="mt-4">
          <h3 className="text-sm text-slate-400 mb-2 uppercase">
            Championship
          </h3>
          <div>{renderMatches(bracket.championship)}</div>

          {bracket.consolation && bracket.consolation.length > 0 && (
            <>
              <h3 className="text-sm text-slate-400 mb-2 uppercase mt-4">
                Consolation
              </h3>
              <div>{renderMatches(bracket.consolation)}</div>
            </>
          )}
        </div>
      )}

      {!loading && !bracket && (
        <div className="text-slate-500 mt-2 italic">No bracket data.</div>
      )}
    </details>
  );
}
