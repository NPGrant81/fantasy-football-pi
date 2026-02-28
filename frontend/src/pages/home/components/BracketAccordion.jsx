import React, { useState, useEffect } from 'react';
import apiClient from '@api/client';

export default function BracketAccordion({ leagueId: propLeagueId }) {
  const [open, setOpen] = useState(false);
  const [bracket, setBracket] = useState(null);
  const [loading, setLoading] = useState(false);
  // avoid accessing localStorage during SSR or before it exists
  const [leagueId, setLeagueId] = useState(propLeagueId || null);
  const [season, setSeason] = useState(new Date().getFullYear());
  const [seasons, setSeasons] = useState([]);
  const [view, setView] = useState('championship'); // or 'consolation'

  useEffect(() => {
    if (!propLeagueId && typeof window !== 'undefined') {
      const stored = window.localStorage && window.localStorage.getItem('fantasyLeagueId');
      if (stored) setLeagueId(stored);
    }
  }, [propLeagueId]);

  // load list of available seasons so user can pick archived years
  useEffect(() => {
    if (!leagueId) return;
    const fetchSeasons = async () => {
      try {
        const res = await apiClient.get(`/playoffs/seasons?league_id=${leagueId}`);
        // some backend variants accidentally wrap the list in an object
        let list = res.data;
        if (!Array.isArray(list) && list && Array.isArray(list.seasons)) {
          list = list.seasons;
        }
        if (!Array.isArray(list)) {
          list = [];
        }
        setSeasons(list);
        if (list.length > 0) {
          setSeason(list[0]); // default to most recent
        }
      } catch {
        // ignore, seasons list is optional
      }
    };
    fetchSeasons();
  }, [leagueId]);

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
    <>
      {/* season selector for archived years */}
      {seasons.length > 0 && (
        <div className="mb-4 flex items-center gap-2">
          <label className="text-xs">Season:</label>
          <select
            className="bg-slate-800 text-white p-1 rounded"
            value={season}
            onChange={(e) => setSeason(Number(e.target.value))}
          >
            {seasons.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      )}

      <details
        className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 shadow-xl"
        onToggle={(e) => setOpen(e.target.open)}
      >
      <summary className="cursor-pointer text-lg font-bold text-white flex items-center justify-start">
        Playoff Bracket
      </summary>

      {loading && <div className="text-slate-400 mt-2">Loading...</div>}
      {!loading && bracket && (
        <div className="mt-4">
          {/* selector for which bracket view to display */}
          <div className="mb-4 flex items-center gap-2">
            <label className="text-xs">View:</label>
            <select
              className="bg-slate-800 text-white p-1 rounded"
              value={view}
              onChange={(e) => setView(e.target.value)}
            >
              <option value="championship">Championship</option>
              <option value="consolation">Toilet Bowl</option>
            </select>
          </div>
          <h3 className="text-sm text-slate-400 mb-2 uppercase">
            {view === 'championship' ? 'Championship' : 'Toilet Bowl'}
          </h3>
          <div>
            {renderMatches(
              view === 'championship'
                ? bracket.championship
                : bracket.consolation
            )}
          </div>
        </div>
      )}

      {!loading && !bracket && (
        <div className="text-slate-500 mt-2 italic">No bracket data.</div>
      )}

      {/* season picker above the summary */}
    </details>
    </>
  );
}
