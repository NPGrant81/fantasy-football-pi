import React, { useMemo, useState, useEffect, useCallback } from 'react';
import { FiCheckCircle, FiClock, FiRepeat, FiSearch, FiX } from 'react-icons/fi';
import { EmptyState, LoadingState } from '@components/common/AsyncState';
import InlineError from '@components/common/InlineError';
import {
  fetchCurrentUser,
  fetchLeagueOwners,
  fetchOwnerRoster,
} from '@api/commonApi';
import { normalizeApiError } from '@api/fetching';
import { buttonPrimary, buttonSecondary, cardSurface, inputBase } from '@utils/uiStandards';
import {
  buildCashRecommendation,
  computeNetLineupImpact,
  computeLineupAdjustedValue,
  computePlayerValue,
  deriveRiskPenalty,
  deriveTrendAdjustment,
  deriveVolatilityPenalty,
  gradeForDelta,
  normalizePosition,
  summarizeTradeSide,
} from './tradeAnalyzerLogic';

export default function TradeAnalyzer() {
  const [owners, setOwners] = useState([]);
  const [teamA, setTeamA] = useState(null);
  const [teamB, setTeamB] = useState(null);
  const [teamError, setTeamError] = useState('');
  const [loadingOwners, setLoadingOwners] = useState(true);

  const [rosterA, setRosterA] = useState([]);
  const [rosterB, setRosterB] = useState([]);
  const [loadingRosterA, setLoadingRosterA] = useState(false);
  const [loadingRosterB, setLoadingRosterB] = useState(false);

  const [selectedAIds, setSelectedAIds] = useState([]);
  const [selectedBIds, setSelectedBIds] = useState([]);

  const [searchA, setSearchA] = useState('');
  const [searchB, setSearchB] = useState('');
  const [posFilterA, setPosFilterA] = useState('ALL');
  const [posFilterB, setPosFilterB] = useState('ALL');

  const [analysisError, setAnalysisError] = useState('');

  const positions = ['ALL', 'QB', 'RB', 'WR', 'TE', 'FLEX', 'DST', 'K'];

  const gradeTone = (grade) => {
    if (grade.startsWith('A')) return 'text-emerald-300';
    if (grade.startsWith('B')) return 'text-cyan-300';
    if (grade.startsWith('C')) return 'text-amber-300';
    return 'text-rose-300';
  };

  const loadOwners = useCallback(async () => {
    setLoadingOwners(true);
    try {
      const user = await fetchCurrentUser();
      const lid = user?.league_id;
      if (!lid) {
        setOwners([]);
        return;
      }
      const ownersPayload = await fetchLeagueOwners(lid);
      const nextOwners = Array.isArray(ownersPayload) ? ownersPayload : [];
      setOwners(nextOwners);
      if (!teamA && nextOwners.length) setTeamA(nextOwners[0].id);
      if (!teamB && nextOwners.length > 1) setTeamB(nextOwners[1].id);
    } catch (err) {
      console.error(err);
      setAnalysisError(normalizeApiError(err, 'Failed to load team selectors.'));
    } finally {
      setLoadingOwners(false);
    }
  }, [teamA, teamB]);

  useEffect(() => {
    loadOwners();
  }, [loadOwners]);

  useEffect(() => {
    if (!teamA) return;
    let isMounted = true;
    setLoadingRosterA(true);
    fetchOwnerRoster(teamA)
      .then((payload) => {
        if (!isMounted) return;
        setRosterA(Array.isArray(payload?.players) ? payload.players : []);
      })
      .catch((err) => {
        if (!isMounted) return;
        setRosterA([]);
        setAnalysisError(normalizeApiError(err, 'Failed to load Team A roster.'));
      })
      .finally(() => {
        if (isMounted) setLoadingRosterA(false);
      });
    return () => {
      isMounted = false;
    };
  }, [teamA]);

  useEffect(() => {
    if (!teamB) return;
    let isMounted = true;
    setLoadingRosterB(true);
    fetchOwnerRoster(teamB)
      .then((payload) => {
        if (!isMounted) return;
        setRosterB(Array.isArray(payload?.players) ? payload.players : []);
      })
      .catch((err) => {
        if (!isMounted) return;
        setRosterB([]);
        setAnalysisError(normalizeApiError(err, 'Failed to load Team B roster.'));
      })
      .finally(() => {
        if (isMounted) setLoadingRosterB(false);
      });
    return () => {
      isMounted = false;
    };
  }, [teamB]);

  useEffect(() => {
    if (teamA && teamB && Number(teamA) === Number(teamB)) {
      setTeamError('Team A and Team B must be different teams.');
      return;
    }
    setTeamError('');
  }, [teamA, teamB]);

  const selectedAPlayers = useMemo(
    () => rosterA.filter((player) => selectedAIds.includes(player.player_id)),
    [rosterA, selectedAIds]
  );

  const selectedBPlayers = useMemo(
    () => rosterB.filter((player) => selectedBIds.includes(player.player_id)),
    [rosterB, selectedBIds]
  );

  const filteredRoster = useCallback((rosterRows, query, position) => {
    const q = String(query || '').trim().toLowerCase();
    return rosterRows.filter((player) => {
      const pos = normalizePosition(player.position);
      const matchesPos = position === 'ALL' || pos === position || (position === 'FLEX' && ['RB', 'WR', 'TE'].includes(pos));
      if (!matchesPos) return false;
      if (!q) return true;
      return (
        String(player.name || '').toLowerCase().includes(q) ||
        String(player.nfl_team || '').toLowerCase().includes(q)
      );
    });
  }, []);

  const visibleA = useMemo(
    () => filteredRoster(rosterA, searchA, posFilterA),
    [rosterA, searchA, posFilterA, filteredRoster]
  );
  const visibleB = useMemo(
    () => filteredRoster(rosterB, searchB, posFilterB),
    [rosterB, searchB, posFilterB, filteredRoster]
  );

  const totalA = useMemo(() => summarizeTradeSide(selectedAPlayers), [selectedAPlayers]);
  const totalB = useMemo(() => summarizeTradeSide(selectedBPlayers), [selectedBPlayers]);
  const delta = useMemo(() => Number((totalA - totalB).toFixed(2)), [totalA, totalB]);

  const impactA = useMemo(
    () => computeNetLineupImpact({
      incomingPlayers: selectedBPlayers,
      outgoingPlayers: selectedAPlayers,
      fullRoster: rosterA,
    }),
    [selectedAPlayers, selectedBPlayers, rosterA]
  );

  const impactB = useMemo(
    () => computeNetLineupImpact({
      incomingPlayers: selectedAPlayers,
      outgoingPlayers: selectedBPlayers,
      fullRoster: rosterB,
    }),
    [selectedAPlayers, selectedBPlayers, rosterB]
  );

  const impactDelta = useMemo(() => Number((impactA - impactB).toFixed(2)), [impactA, impactB]);

  const [gradeA, gradeB] = useMemo(() => gradeForDelta(impactDelta), [impactDelta]);

  const positionRows = useMemo(() => {
    const bucket = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'DST', 'K'];
    const forTeam = (players) => {
      const map = Object.fromEntries(bucket.map((k) => [k, 0]));
      players.forEach((player) => {
        const pos = normalizePosition(player.position);
        const value = computeLineupAdjustedValue(player);
        if (['RB', 'WR', 'TE'].includes(pos)) {
          map.FLEX += value;
        }
        if (map[pos] != null) {
          map[pos] += value;
        }
      });
      return map;
    };

    const aMap = forTeam(selectedAPlayers);
    const bMap = forTeam(selectedBPlayers);
    return bucket.map((position) => ({
      position,
      a: Number(aMap[position].toFixed(2)),
      b: Number(bMap[position].toFixed(2)),
    }));
  }, [selectedAPlayers, selectedBPlayers]);

  const positionInsights = useMemo(() => {
    const bucket = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'DST', 'K'];
    const build = (players, position) => {
      const match = players.filter((player) => {
        const pos = normalizePosition(player.position);
        return position === 'FLEX' ? ['RB', 'WR', 'TE'].includes(pos) : pos === position;
      });
      if (!match.length) {
        return {
          names: 'No selected contributors',
          starterImpact: '0 starter / 0 bench',
          trend: 'stable',
          volatility: 'low',
          risk: 'low',
        };
      }

      const values = match.map((player) => computePlayerValue(player));
      const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
      const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
      const stdDev = Math.sqrt(variance);

      const starterCount = match.filter((player) => player.is_starter).length;
      const benchCount = Math.max(0, match.length - starterCount);
      const highProjection = match.filter((player) => Number(player.projected_points || 0) >= 14).length;
      const byeRisk = match.filter((player) => player.bye_week).length;

      return {
        names: match.slice(0, 3).map((player) => player.name).join(', '),
        starterImpact: `${starterCount} starter / ${benchCount} bench`,
        trend:
          deriveTrendAdjustment({
            trend_adjustment: (highProjection - Math.max(0, match.length - highProjection)) * 0.5,
          }) > 0
            ? 'upward'
            : 'flat',
        volatility:
          deriveVolatilityPenalty({ volatility_penalty: stdDev }) >= 1.5
            ? 'medium-high'
            : 'low',
        risk: deriveRiskPenalty({ risk_penalty: byeRisk }) >= 1 ? 'elevated' : 'low',
      };
    };

    const table = {};
    bucket.forEach((position) => {
      table[position] = {
        a: build(selectedAPlayers, position),
        b: build(selectedBPlayers, position),
      };
    });
    return table;
  }, [selectedAPlayers, selectedBPlayers]);

  const cashRecommendation = useMemo(() => buildCashRecommendation(impactDelta), [impactDelta]);

  const buildRationale = () => {
    if (impactDelta > 2) {
      return 'Team A gains more near-term lineup value after replacement effects.';
    }
    if (impactDelta < -2) {
      return 'Team B gains more near-term lineup value after replacement effects.';
    }
    return 'Trade is close to balanced with similar projected value exchange.';
  };

  const togglePlayer = (side, playerId) => {
    const setter = side === 'A' ? setSelectedAIds : setSelectedBIds;
    setter((prev) => (prev.includes(playerId) ? prev.filter((id) => id !== playerId) : [...prev, playerId]));
  };

  const removePlayer = (side, playerId) => {
    const setter = side === 'A' ? setSelectedAIds : setSelectedBIds;
    setter((prev) => prev.filter((id) => id !== playerId));
  };

  const ownerName = (ownerId) => owners.find((owner) => Number(owner.id) === Number(ownerId))?.team_name
    || owners.find((owner) => Number(owner.id) === Number(ownerId))?.username
    || `Owner ${ownerId}`;

  const selectorPanel = ({
    side,
    team,
    setTeam,
    visible,
    selectedIds,
    search,
    setSearch,
    posFilter,
    setPosFilter,
    loading,
  }) => (
    <section className={`${cardSurface} space-y-3`}>
      <h4 className="text-sm font-black uppercase tracking-wider text-cyan-300">Team {side}</h4>
      <label className="text-xs text-slate-400">
        Team
        <select
          value={team || ''}
          onChange={(event) => setTeam(Number(event.target.value) || null)}
          className={`${inputBase} mt-1`}
          aria-label={`Team ${side} selector`}
        >
          <option value="">Select team</option>
          {owners.map((owner) => (
            <option key={owner.id} value={owner.id}>
              {owner.team_name || owner.username || `Owner ${owner.id}`}
            </option>
          ))}
        </select>
      </label>

      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        <label className="text-xs text-slate-400">
          Search
          <div className="relative mt-1">
            <FiSearch className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Find player"
              className={`${inputBase} pl-8`}
            />
          </div>
        </label>
        <label className="text-xs text-slate-400">
          Position
          <select
            value={posFilter}
            onChange={(event) => setPosFilter(event.target.value)}
            className={`${inputBase} mt-1`}
          >
            {positions.map((position) => (
              <option key={position} value={position}>{position}</option>
            ))}
          </select>
        </label>
      </div>

      {loading ? (
        <LoadingState message="Loading roster..." className="text-xs text-slate-500" />
      ) : null}

      <div className="max-h-56 space-y-2 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950/50 p-2">
        {visible.map((player) => {
          const checked = selectedIds.includes(player.player_id);
          return (
            <label
              key={player.player_id}
              className="flex cursor-pointer items-center justify-between gap-2 rounded border border-slate-800 px-2 py-1 text-xs text-slate-300 hover:border-slate-700"
            >
              <span className="min-w-0 truncate">
                {player.name} ({normalizePosition(player.position)})
              </span>
              <input
                type="checkbox"
                checked={checked}
                onChange={() => togglePlayer(side, player.player_id)}
                aria-label={`${player.name} select`}
              />
            </label>
          );
        })}
        {!visible.length ? (
          <EmptyState
            message="No players match current filter."
            className="text-xs text-slate-500"
          />
        ) : null}
      </div>

      <div className="hidden space-y-2 md:block">
        {(side === 'A' ? selectedAPlayers : selectedBPlayers).map((player) => (
          <div
            key={`${side}-${player.player_id}`}
            className="flex items-center justify-between rounded border border-slate-800 bg-slate-950/40 px-2 py-1 text-xs"
          >
            <div className="min-w-0">
              <div className="truncate text-slate-100">{player.name}</div>
              <div className="text-slate-500">
                {normalizePosition(player.position)} | {player.nfl_team || 'N/A'} | Bye {player.bye_week || '--'} | Val {computeLineupAdjustedValue(player)}
              </div>
            </div>
            <div className="ml-2 flex items-center gap-2">
              <span title={player.is_starter ? 'Starter impact' : 'Bench depth impact'}>
                {player.is_starter ? <FiCheckCircle className="text-emerald-300" /> : <FiClock className="text-amber-300" />}
              </span>
              <button
                type="button"
                className={buttonSecondary}
                onClick={() => removePlayer(side, player.player_id)}
                aria-label={`Remove ${player.name}`}
              >
                <FiX />
              </button>
            </div>
          </div>
        ))}
      </div>

      <details className="md:hidden rounded border border-slate-800 bg-slate-950/30 p-2">
        <summary className="cursor-pointer text-xs font-bold uppercase tracking-wider text-slate-300">
          Selected Players ({(side === 'A' ? selectedAPlayers : selectedBPlayers).length})
        </summary>
        <div className="mt-2 space-y-2">
          {(side === 'A' ? selectedAPlayers : selectedBPlayers).map((player) => (
            <div
              key={`mobile-${side}-${player.player_id}`}
              className="flex items-center justify-between rounded border border-slate-800 bg-slate-950/40 px-2 py-1 text-xs"
            >
              <div className="min-w-0">
                <div className="truncate text-slate-100">{player.name}</div>
                <div className="text-slate-500">
                  {normalizePosition(player.position)} | {player.nfl_team || 'N/A'} | Bye {player.bye_week || '--'} | Val {computeLineupAdjustedValue(player)}
                </div>
              </div>
              <button
                type="button"
                className={buttonSecondary}
                onClick={() => removePlayer(side, player.player_id)}
                aria-label={`Remove ${player.name}`}
              >
                <FiX />
              </button>
            </div>
          ))}
          {!(side === 'A' ? selectedAPlayers : selectedBPlayers).length ? (
            <EmptyState
              message="No players selected yet."
              className="text-xs text-slate-500"
            />
          ) : null}
        </div>
      </details>
    </section>
  );

  return (
    <div className="space-y-6 text-white">
      {teamError ? (
        <InlineError title="Team selection conflict" message={teamError} />
      ) : null}

      {analysisError ? (
        <InlineError title="Trade analyzer error" message={analysisError} onRetry={loadOwners} />
      ) : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {selectorPanel({
          side: 'A',
          team: teamA,
          setTeam: setTeamA,
          visible: visibleA,
          selectedIds: selectedAIds,
          search: searchA,
          setSearch: setSearchA,
          posFilter: posFilterA,
          setPosFilter: setPosFilterA,
          loading: loadingOwners || loadingRosterA,
        })}

        {selectorPanel({
          side: 'B',
          team: teamB,
          setTeam: setTeamB,
          visible: visibleB,
          selectedIds: selectedBIds,
          search: searchB,
          setSearch: setSearchB,
          posFilter: posFilterB,
          setPosFilter: setPosFilterB,
          loading: loadingOwners || loadingRosterB,
        })}
      </div>

      <section className={`${cardSurface} mx-auto w-full max-w-5xl space-y-4`}>
        <div className="flex items-center justify-center gap-2 text-sm font-bold uppercase tracking-wider text-cyan-300">
          <FiRepeat /> Total Trade Value Comparison
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded border border-slate-800 bg-slate-950/40 p-3 text-center">
            <div className="text-xs text-slate-400">{ownerName(teamA)} Total</div>
            <div className="text-2xl font-black text-cyan-300">{totalA.toFixed(2)}</div>
          </div>
          <div className="rounded border border-slate-800 bg-slate-950/40 p-3 text-center">
            <div className="text-xs text-slate-400">Difference</div>
            <div className={`text-2xl font-black ${delta >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
              {delta >= 0 ? '+' : ''}{delta.toFixed(2)}
            </div>
          </div>
          <div className="rounded border border-slate-800 bg-slate-950/40 p-3 text-center">
            <div className="text-xs text-slate-400">{ownerName(teamB)} Total</div>
            <div className="text-2xl font-black text-indigo-300">{totalB.toFixed(2)}</div>
          </div>
        </div>

        <div className="space-y-2">
          {positionRows.map((row) => {
            const maxPos = Math.max(row.a, row.b, 1);
            const insight = positionInsights[row.position] || {
              a: { names: 'No selected contributors', starterImpact: '0 starter / 0 bench', trend: 'stable', volatility: 'low', risk: 'low' },
              b: { names: 'No selected contributors', starterImpact: '0 starter / 0 bench', trend: 'stable', volatility: 'low', risk: 'low' },
            };
            return (
              <div key={row.position} className="rounded border border-slate-800 bg-slate-950/40 p-2 text-xs">
                <div className="mb-1 flex items-center justify-between text-slate-400">
                  <span>{row.position}</span>
                  <span>{row.a.toFixed(1)} vs {row.b.toFixed(1)}</span>
                </div>
                <div className="grid grid-cols-2 gap-2" role="img" aria-label={`${row.position} trade value bars`}>
                  <div className="h-2 rounded bg-slate-900">
                    <div
                      className="h-full rounded bg-cyan-500"
                      style={{ width: `${(row.a / maxPos) * 100}%` }}
                      title={`${ownerName(teamA)} ${row.position}\nContributors: ${insight.a.names}\nLineup impact: ${insight.a.starterImpact}\nTrend: ${insight.a.trend}\nVolatility: ${insight.a.volatility}\nRisk: ${insight.a.risk}`}
                    />
                  </div>
                  <div className="h-2 rounded bg-slate-900">
                    <div
                      className="h-full rounded bg-indigo-500"
                      style={{ width: `${(row.b / maxPos) * 100}%` }}
                      title={`${ownerName(teamB)} ${row.position}\nContributors: ${insight.b.names}\nLineup impact: ${insight.b.starterImpact}\nTrend: ${insight.b.trend}\nVolatility: ${insight.b.volatility}\nRisk: ${insight.b.risk}`}
                    />
                  </div>
                </div>
                <div className="mt-1 text-[11px] text-slate-500">
                  A: {insight.a.starterImpact} | B: {insight.b.starterImpact}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <div className="mx-auto grid w-full max-w-4xl grid-cols-1 gap-4 md:grid-cols-2">
        <section className={`${cardSurface} space-y-2`}>
          <h4 className="text-sm font-black uppercase tracking-wider text-slate-200">Trade Summary</h4>
          <div className="text-sm text-slate-300">{ownerName(teamA)}: <span className={gradeTone(gradeA)}>{gradeA}</span></div>
          <div className="text-sm text-slate-300">{ownerName(teamB)}: <span className={gradeTone(gradeB)}>{gradeB}</span></div>
          <div className="text-xs text-slate-500">Lineup impact A/B: {impactA.toFixed(2)} / {impactB.toFixed(2)}</div>
          <div className="text-xs text-slate-400">{buildRationale()}</div>
        </section>

        {cashRecommendation ? (
          <section className={`${cardSurface} border-amber-700/60 space-y-2`}>
            <h4 className="text-sm font-black uppercase tracking-wider text-amber-300">Draft Cash Recommendation</h4>
            <div className="text-lg font-black text-amber-200">${cashRecommendation.amount}</div>
            <div className="text-xs text-slate-300">Tier: {cashRecommendation.tier}</div>
            <div className="text-xs text-slate-400">{cashRecommendation.explanation}</div>
          </section>
        ) : (
          <section className={`${cardSurface} space-y-2`}>
            <h4 className="text-sm font-black uppercase tracking-wider text-emerald-300">Draft Cash Recommendation</h4>
            <div className="text-xs text-slate-400">Fair range: no cash adjustment required.</div>
          </section>
        )}
      </div>

      <div className="flex justify-end">
        <button type="button" className={buttonPrimary} disabled={!!teamError || !teamA || !teamB}>
          Prepare Trade Proposal
        </button>
      </div>
    </div>
  );
}
