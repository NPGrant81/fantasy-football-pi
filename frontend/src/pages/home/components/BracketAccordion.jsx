import React, { useState, useEffect } from 'react';
import apiClient from '@api/client';
import { LoadingState } from '@components/common/AsyncState';
/* ignore-breakpoints */

export default function BracketAccordion({ leagueId: propLeagueId }) {
  const [open, setOpen] = useState(false);
  const [bracket, setBracket] = useState(null);
  const [loading, setLoading] = useState(false);
  // avoid accessing localStorage during SSR or before it exists
  const [leagueId, setLeagueId] = useState(propLeagueId || null);
  const currentSeason = new Date().getFullYear();
  const [season, setSeason] = useState(currentSeason);
  const [seasons, setSeasons] = useState([]);
  const [view, setView] = useState('championship'); // or 'consolation'
  const [historicalMode, setHistoricalMode] = useState(false);
  const [ownerNameById, setOwnerNameById] = useState({});

  const formatTiebreakToken = (token) => {
    if (!token) return '-';
    return String(token).replaceAll('_', ' ');
  };

  const formatMetaSource = (source) => {
    if (!source) return 'Live data';
    return String(source).replaceAll('_', ' ');
  };

  const hasConsolation = Boolean(bracket?.seeding_policy?.playoff_consolation);

  useEffect(() => {
    if (view === 'consolation' && !hasConsolation) {
      setView('championship');
    }
  }, [view, hasConsolation]);

  const renderTeamLine = ({
    teamId,
    seed,
    isDivisionWinner,
    divisionName,
    align = 'left',
  }) => {
    const alignmentClass = align === 'right' ? 'text-right' : 'text-left';
    return (
      <div className={`flex flex-col ${alignmentClass}`}>
        <span className="font-semibold text-slate-100">
          {teamId ? ownerNameById[Number(teamId)] || `Team ${teamId}` : 'TBD'}
        </span>
        <div className="flex flex-wrap gap-1 mt-1">
          {seed ? (
            <span className="rounded border border-slate-600 bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-300">
              Seed {seed}
            </span>
          ) : null}
          {isDivisionWinner ? (
            <span className="rounded border border-cyan-700 bg-cyan-950/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-cyan-300">
              Division Winner
            </span>
          ) : null}
          {divisionName ? (
            <span className="rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
              {divisionName}
            </span>
          ) : null}
        </div>
      </div>
    );
  };

  useEffect(() => {
    if (!propLeagueId && typeof window !== 'undefined') {
      const stored =
        window.localStorage && window.localStorage.getItem('fantasyLeagueId');
      if (stored) setLeagueId(stored);
    }
  }, [propLeagueId]);

  useEffect(() => {
    if (!leagueId) return;

    const fetchOwnerNames = async () => {
      try {
        const res = await apiClient.get(`/leagues/owners?league_id=${leagueId}`);
        const rows = Array.isArray(res.data) ? res.data : [];
        const map = {};
        for (const owner of rows) {
          map[Number(owner.id)] = owner.team_name || owner.username || `Team ${owner.id}`;
        }
        setOwnerNameById(map);
      } catch {
        setOwnerNameById({});
      }
    };

    fetchOwnerNames();
  }, [leagueId]);

  // load list of available seasons for optional historical lookup
  useEffect(() => {
    if (!leagueId) return;
    const fetchSeasons = async () => {
      try {
        const res = await apiClient.get(
          `/playoffs/seasons?league_id=${leagueId}`
        );
        // some backend variants accidentally wrap the list in an object
        let list = res.data;
        if (!Array.isArray(list) && list && Array.isArray(list.seasons)) {
          list = list.seasons;
        }
        if (!Array.isArray(list)) {
          list = [];
        }
        setSeasons(list);
        if (historicalMode && list.length > 0 && !list.includes(season)) {
          setSeason(list[0]);
        }
      } catch {
        // ignore, seasons list is optional
      }
    };
    fetchSeasons();
  }, [leagueId, historicalMode, season]);

  useEffect(() => {
    if (!historicalMode) {
      setSeason(currentSeason);
    } else if (seasons.length > 0 && !seasons.includes(season)) {
      setSeason(seasons[0]);
    }
  }, [historicalMode, currentSeason, seasons, season]);

  useEffect(() => {
    // only fetch when the panel opens and we have a league id
    if (!open || !leagueId) return;

    const fetchBracket = async () => {
      setLoading(true);
      try {
        if (!historicalMode) {
          // Keep current-season bracket aligned with standings/settings.
          await apiClient.post('/playoffs/generate', {
            league_id: Number(leagueId),
            season: currentSeason,
          });
        }

        const targetSeason = historicalMode ? season : currentSeason;
        const res = await apiClient.get(
          `/playoffs/bracket?league_id=${leagueId}&season=${targetSeason}`
        );
        setBracket(res.data);
      } catch {
        setBracket(null);
      } finally {
        setLoading(false);
      }
    };

    fetchBracket();
  }, [open, leagueId, season, historicalMode, currentSeason]);

  const renderMatchCard = (m = {}) => {
    const id = m.match_id || 'unknown';
    return (
      <div
        key={id}
        className="border border-slate-700 rounded p-2 mb-2 bg-slate-900/30 min-w-[220px]"
      >
        <div className="text-xs text-slate-400 flex items-center justify-between gap-2">
          <span>{id}</span>
          {m.round ? (
            <span className="rounded border border-slate-700 px-1.5 py-0.5 uppercase tracking-wide text-[10px]">
              Round {m.round}
            </span>
          ) : null}
        </div>
        {m.is_bye ? (
          <div className="text-sm text-yellow-400">
            BYE - {m.team_1_id ? ownerNameById[Number(m.team_1_id)] || `Team ${m.team_1_id}` : 'TBD'} advances
          </div>
        ) : (
          <div className="text-sm flex justify-between gap-2">
            {renderTeamLine({
              teamId: m.team_1_id,
              seed: m.team_1_seed,
              isDivisionWinner: m.team_1_is_division_winner,
              divisionName: m.team_1_division_name,
            })}
            <span className="text-slate-400">vs</span>
            {renderTeamLine({
              teamId: m.team_2_id,
              seed: m.team_2_seed,
              isDivisionWinner: m.team_2_is_division_winner,
              divisionName: m.team_2_division_name,
              align: 'right',
            })}
          </div>
        )}
        {m.winner_to ? (
          <div className="mt-2 text-[11px] text-slate-400">Winner advances to next round</div>
        ) : null}
      </div>
    );
  };

  const renderMatches = (matches, bracketType = 'championship') => {
    if (!matches || !Array.isArray(matches)) return null;
    const grouped = matches.reduce((acc, match) => {
      const key = String(match.round || 1);
      if (!acc[key]) acc[key] = [];
      acc[key].push(match);
      return acc;
    }, {});
    const roundKeys = Object.keys(grouped)
      .map((r) => Number(r))
      .sort((a, b) => a - b);
    const roundLabels = bracket?.seeding_policy?.round_labels?.[bracketType] || {};

    return (
      <div className="overflow-x-auto">
        <div className="flex gap-4 pb-2 min-w-max">
          {roundKeys.map((roundNum) => (
            <div key={roundNum} className="min-w-[250px]">
              <div className="mb-2 text-xs uppercase tracking-wider text-slate-400">
                {roundLabels[String(roundNum)] || `Round ${roundNum}`}
              </div>
              {grouped[String(roundNum)].map((match) => renderMatchCard(match))}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setHistoricalMode((prev) => !prev)}
          className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-100 hover:bg-slate-700"
        >
          {historicalMode ? 'Show Current Season' : 'See Historical'}
        </button>

        {historicalMode && seasons.length > 0 ? (
          <>
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
          </>
        ) : null}
      </div>

      <details
        className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 shadow-xl"
        onToggle={(e) => setOpen(e.target.open)}
      >
        <summary className="cursor-pointer text-lg font-bold text-white flex items-center justify-start">
          Playoff Bracket
        </summary>

        {loading && <LoadingState message="Loading..." className="mt-2" />}
        {!loading && bracket && (
          <div className="mt-4">
            {bracket.meta ? (
              <div className="mb-4 rounded border border-amber-700/60 bg-amber-950/30 p-3 text-xs text-amber-100">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-bold uppercase tracking-wider text-amber-200">
                    Bracket Source
                  </span>
                  <span className="rounded border border-amber-700/70 bg-amber-900/40 px-2 py-1 uppercase tracking-wide text-[10px] text-amber-100">
                    {formatMetaSource(bracket.meta.source)}
                  </span>
                  {bracket.meta.is_partial ? (
                    <span className="rounded border border-amber-600/70 bg-amber-900/20 px-2 py-1 uppercase tracking-wide text-[10px] text-amber-200">
                      Partial Data
                    </span>
                  ) : null}
                </div>
                {Array.isArray(bracket.meta.warnings) && bracket.meta.warnings.length > 0 ? (
                  <div className="mt-2 space-y-1 text-amber-100/90">
                    {bracket.meta.warnings.map((warning) => (
                      <div key={warning}>{warning}</div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            {bracket.seeding_policy ? (
              <div className="mb-4 rounded border border-slate-700 bg-slate-900/40 p-3">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">
                  Seeding Policy
                </div>
                <div className="flex flex-wrap gap-2 mb-2">
                  {bracket.seeding_policy.division_winners_top_seeds ? (
                    <span className="rounded border border-cyan-700 bg-cyan-950/60 px-2 py-1 text-[10px] uppercase tracking-wide text-cyan-300">
                      Division Winners Top Seeds
                    </span>
                  ) : null}
                  {bracket.seeding_policy.wildcards_by_overall_record ? (
                    <span className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-[10px] uppercase tracking-wide text-slate-300">
                      Wildcards by Overall Record
                    </span>
                  ) : null}
                </div>
                {Array.isArray(bracket.seeding_policy.tiebreak_chain) && (
                  <div className="text-xs text-slate-400">
                    Tiebreak chain:{' '}
                    {bracket.seeding_policy.tiebreak_chain
                      .map((token) => formatTiebreakToken(token))
                      .join(' > ')}
                  </div>
                )}
              </div>
            ) : null}

            {/* selector for which bracket view to display */}
            <div className="mb-4 flex items-center gap-2">
              <label className="text-xs">View:</label>
              <select
                className="bg-slate-800 text-white p-1 rounded"
                value={view}
                onChange={(e) => setView(e.target.value)}
              >
                <option value="championship">Champion</option>
                {hasConsolation ? (
                  <option value="consolation">Toilet Bowl</option>
                ) : null}
              </select>
            </div>
            <h3 className="text-sm text-slate-400 mb-2 uppercase">
              {view === 'championship' ? 'Champion' : 'Toilet Bowl'}
            </h3>
            {view === 'championship' && bracket.champion ? (
              <div className="mb-3 text-xs text-emerald-300">
                Champion: {bracket.champion.team_name}
              </div>
            ) : null}
            {view === 'consolation' && bracket.toilet_bowl_winner ? (
              <div className="mb-3 text-xs text-cyan-300">
                Toilet Bowl Winner: {bracket.toilet_bowl_winner.team_name}
              </div>
            ) : null}
            <div>
              {renderMatches(
                view === 'championship'
                  ? bracket.championship
                  : bracket.consolation,
                view
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
