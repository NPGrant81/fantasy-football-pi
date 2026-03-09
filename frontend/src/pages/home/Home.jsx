// frontend/src/pages/Home.jsx
import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';
import { Link } from 'react-router-dom';
import FeedPill from '../../components/feeds/FeedPill';
import { FiAward, FiActivity } from 'react-icons/fi';
import {
  cardSurface,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
  tableHead,
  tableSurface,
} from '@utils/uiStandards';

export default function Home({ username }) {
  const [standings, setStandings] = useState([]);
  const [sortField, setSortField] = useState('wins');
  const [sortAsc, setSortAsc] = useState(false);

  const normalizeStandingRow = (row) => {
    const wins = Number(row?.wins ?? row?.overall_record?.wins ?? 0);
    const losses = Number(row?.losses ?? row?.overall_record?.losses ?? 0);
    const ties = Number(row?.ties ?? row?.overall_record?.ties ?? 0);
    const pf = Number(
      row?.pf ?? row?.points_for ?? row?.standings_metrics?.points_for ?? 0
    );
    const pa = Number(
      row?.pa ?? row?.points_against ?? row?.standings_metrics?.points_against ?? 0
    );

    return {
      ...row,
      wins,
      losses,
      ties,
      pf,
      pa,
    };
  };

  const sortedStandings = [...standings]
    .map(normalizeStandingRow)
    .sort((a, b) => {
      const direction = sortAsc ? 1 : -1;

      if (sortField === 'record') {
        const aRecord = [a.wins, -a.losses, a.ties, a.pf];
        const bRecord = [b.wins, -b.losses, b.ties, b.pf];
        for (let idx = 0; idx < aRecord.length; idx += 1) {
          if (aRecord[idx] < bRecord[idx]) return -1 * direction;
          if (aRecord[idx] > bRecord[idx]) return 1 * direction;
        }
        return 0;
      }

      let av = a[sortField] ?? 0;
      let bv = b[sortField] ?? 0;
      if (sortField === 'team_name' || sortField === 'username') {
        av = String(av).toLowerCase();
        bv = String(bv).toLowerCase();
      }
      if (av < bv) return -1 * direction;
      if (av > bv) return 1 * direction;
      return 0;
    });

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const sortIndicator = (field) => {
    if (sortField !== field) return '';
    return sortAsc ? ' ▲' : ' ▼';
  };
  const [news, setNews] = useState([]);
  const [topFreeAgents, setTopFreeAgents] = useState([]);
  const [leagueName, setLeagueName] = useState('');
  const leagueId = localStorage.getItem('fantasyLeagueId');

  const displayRankReason = (owner) => {
    const reason = owner?.tiebreak_context?.rank_reason;
    if (!reason) return '-';
    return String(reason).replaceAll('_', ' ');
  };

  useEffect(() => {
    if (!leagueId) return;
    // Fetch league name
    apiClient
      .get(`/leagues/${leagueId}`)
      .then((res) => setLeagueName(res.data.name))
      .catch(() => setLeagueName('League'));
    // Fetch standings (owners, sorted by points for desc, then W-L)
    apiClient
      .get(`/leagues/owners?league_id=${leagueId}`)
      .then((res) => setStandings(res.data))
      .catch(() => setStandings([]));
    // Fetch news (stub: replace with real endpoint if available)
    apiClient
      .get(`/leagues/${leagueId}/news`)
      .then((res) => setNews(res.data))
      .catch(() => setNews([]));

    apiClient
      .get(`/players/top-free-agents?league_id=${leagueId}&limit=10`)
      .then((res) => setTopFreeAgents(Array.isArray(res.data) ? res.data : []))
      .catch(() => setTopFreeAgents([]));
  }, [leagueId]);
  // --- 1.1 CONFIGURATION ---
  // Note: This page currently serves as a static landing.
  // Future 1.2 Data Retrieval for "League News" will go here.

  return (
    <div className={`${pageShell} animate-fade-in`}>
      {/* 2.1 WELCOME BANNER */}
      <div className={`${pageHeader} border-b-0 pb-0`}>
        <h1 className={pageTitle}>{leagueName || 'League Dashboard'}</h1>
        <p className={pageSubtitle}>
          Welcome back,{' '}
          <span className="font-bold text-slate-900 dark:text-white">
            {username}
          </span>
          . Open the menu{' '}
          <span className="inline-block rounded bg-slate-200 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-700 dark:text-yellow-300">
            ☰
          </span>{' '}
          to access the War Room.
        </p>
      </div>

      {/* 2.2 STANDINGS & ACTIVITY GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 2.2.1 STANDINGS MODULE */}
        <div className={`lg:col-span-2 ${cardSurface}`}>
          <div className="flex items-center gap-2 mb-4">
            <FiAward className="text-yellow-500" size={24} />
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">
              Current Standings
            </h2>
          </div>

          <div className={`${tableSurface} overflow-x-auto`}>
            <table className="w-full min-w-[760px] text-sm text-left text-slate-700 dark:text-slate-300">
              <thead className={tableHead}>
                <tr>
                  <th className="px-4 py-3 min-w-[64px]">Rank</th>
                  <th
                    className="px-4 py-3 cursor-pointer min-w-[160px]"
                    onClick={() => handleSort('team_name')}
                  >
                    Team{sortIndicator('team_name')}
                  </th>
                  <th className="px-4 py-3 min-w-[92px]">Div</th>
                  <th
                    className="px-4 py-3 cursor-pointer min-w-[132px]"
                    onClick={() => handleSort('username')}
                  >
                    Owner{sortIndicator('username')}
                  </th>
                  <th
                    className="px-4 py-3 cursor-pointer min-w-[96px]"
                    onClick={() => handleSort('record')}
                  >
                    W-L-T{sortIndicator('record')}
                  </th>
                  <th
                    className="px-4 py-3 cursor-pointer min-w-[84px]"
                    onClick={() => handleSort('pf')}
                  >
                    PF{sortIndicator('pf')}
                  </th>
                  <th
                    className="px-4 py-3 cursor-pointer min-w-[84px]"
                    onClick={() => handleSort('pa')}
                  >
                    PA{sortIndicator('pa')}
                  </th>
                  <th className="px-4 py-3 min-w-[124px]">TB Context</th>
                </tr>
              </thead>
              <tbody>
                {standings.length > 0 ? (
                  <>
                    {sortedStandings.map((owner, idx) => (
                        <tr
                          key={owner.id}
                          className="border-b border-slate-300 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800/40"
                        >
                          <td
                            className={`px-4 py-3 font-bold ${idx === 0 ? 'text-yellow-500' : 'text-slate-600 dark:text-slate-400'}`}
                          >
                            {idx + 1}
                          </td>
                          <td className="px-4 py-3 font-medium text-slate-900 dark:text-white">
                            <Link
                              to={`/team/${owner.id}`}
                              className="hover:text-blue-400 transition-colors"
                            >
                              {owner.team_name || owner.username}
                            </Link>
                          </td>
                          <td className="px-4 py-3">
                            {owner.division_name ? (
                              <span className="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700">
                                {owner.division_name}
                              </span>
                            ) : (
                              '-'
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <Link
                              to={`/team/${owner.id}`}
                              className="hover:text-blue-400 transition-colors"
                            >
                              {owner.username}
                            </Link>
                          </td>
                          <td className="px-4 py-3">
                            {owner.wins}-{owner.losses}-{owner.ties}
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">{owner.pf}</td>
                          <td className="px-4 py-3 text-right tabular-nums">{owner.pa}</td>
                          <td className="px-4 py-3 text-xs capitalize text-slate-500 dark:text-slate-400">
                            {displayRankReason(owner)}
                          </td>
                        </tr>
                      ))}
                  </>
                ) : (
                  <tr>
                    <td
                      colSpan={8}
                      className="text-center py-6 text-slate-500 dark:text-slate-400"
                    >
                      No owners found for this league.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* 2.2.2 RECENT ACTIVITY MODULE */}
        <div className={cardSurface}>
          <div className="flex items-center gap-2 mb-4">
            <FiActivity className="text-blue-500" size={24} />
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">
              League News
            </h2>
          </div>
          <div className="space-y-3">
            {news.length > 0 ? (
              news.map((item, idx) => (
                <FeedPill
                  key={idx}
                  className={`w-full justify-between gap-3 ${item.type === 'info' ? 'border-l-2 border-green-500' : 'border-l-2 border-yellow-500'}`}
                >
                  <span className="text-slate-300 font-bold truncate">
                    {item.title}
                  </span>
                  <span className="text-slate-500 text-xs shrink-0">
                    {item.timestamp}
                  </span>
                </FeedPill>
              ))
            ) : (
              <div className="mt-4 text-center text-xs italic text-slate-500 dark:text-slate-400">
                End of feed
              </div>
            )}
          </div>
        </div>

        <div className={cardSurface}>
          <div className="flex items-center justify-between gap-2 mb-4">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">
              Hot Pickups
            </h2>
            <Link to="/waivers" className="text-xs text-cyan-600 dark:text-cyan-400 hover:underline">
              Full Waiver Wire
            </Link>
          </div>
          <div className="space-y-2">
            {topFreeAgents.length > 0 ? (
              topFreeAgents.map((player, idx) => (
                <div
                  key={player.id}
                  className="rounded-lg border border-slate-300 dark:border-slate-700 p-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-900 dark:text-white">
                        {idx + 1}. {player.name}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">
                        {player.position || 'N/A'} {player.nfl_team ? `- ${player.nfl_team}` : ''}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        Score
                      </div>
                      <div className="text-sm font-bold text-cyan-600 dark:text-cyan-300">
                        {player.pickup_score ?? 0}
                      </div>
                    </div>
                  </div>

                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(player.pickup_reasons || []).map((reason) => (
                      <span
                        key={`${player.id}-${reason}`}
                        className="rounded-full border border-slate-300 dark:border-slate-600 px-2 py-0.5 text-[11px] text-slate-600 dark:text-slate-300"
                      >
                        {reason}
                      </span>
                    ))}
                  </div>

                  <div className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
                    Claims: {player.recent_claim_count ?? 0} · Proj: {player.projected_points ?? 0} · ADP: {player.adp ?? 0}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-xs italic text-slate-500 dark:text-slate-400">
                No pickup candidates yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
