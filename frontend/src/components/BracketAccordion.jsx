import React, { useState, useEffect } from 'react';
import apiClient from '@api/client';

export default function BracketAccordion() {
  const [open, setOpen] = useState(false);
  const [bracket, setBracket] = useState(null);
  const [loading, setLoading] = useState(false);
  // avoid accessing localStorage during SSR or before it exists
  const [leagueId, setLeagueId] = useState(null);
  const season = new Date().getFullYear();

  useEffect(() => {
    if (typeof window !== 'undefined' && window.localStorage) {
      setLeagueId(window.localStorage.getItem('fantasyLeagueId'));
    }
  }, []);

  useEffect(() => {
    // only fetch when the panel opens and we have a league id
    if (!open || !leagueId) return;

    const fetchBracket = async () => {
      setLoading(true);
      try {
        const res = await apiClient.get(
          `/playoffs/bracket?league_id=${leagueId}&season=${season}`
        );
        setBracket(res.data);
      } catch {
        setBracket(null);
      } finally {
        setLoading(false);
      }
    };

    fetchBracket();
  }, [open, leagueId, season]);

  const renderMatches = (matches) => {
    if (!matches || !Array.isArray(matches)) return null;
    return matches.map((m = {}) => {
      const id = m.match_id || 'unknown';
      return (
        <div
          key={id}
          className="border border-slate-700 rounded p-2 mb-2 bg-slate-900/30"
        >
          <div className="text-xs text-slate-400">{id}</div>
          {m.is_bye ? (
            <div className="text-sm text-yellow-400">
              BYE → seed {m.team_1_id || 'TBD'}
            </div>
          ) : (
            <div className="text-sm flex justify-between">
              <span>#{m.team_1_id || 'TBD'}</span>
              <span>vs</span>
              <span>#{m.team_2_id || 'TBD'}</span>
            </div>
          )}
        </div>
      );
    });
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
