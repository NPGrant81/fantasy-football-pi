// frontend/src/pages/Home.jsx
import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';
import { Link } from 'react-router-dom';
import PageTemplate from '@components/layout/PageTemplate';
import { EmptyState } from '@components/common/AsyncState';
import {
  StandardTable,
  StandardTableContainer,
  StandardTableRow,
  StandardTableStateRow,
} from '@components/table/TablePrimitives';
import FeedPill from '../../components/feeds/FeedPill';
import { FiAward, FiActivity } from 'react-icons/fi';
import {
  cardSurface,
  tableCell,
  tableCellNumeric,
  tableHead,
  textCaption,
} from '@utils/uiStandards';

export default function Home({ username }) {
  const [standings, setStandings] = useState([]);
  const [sortField, setSortField] = useState('record');
  const [sortAsc, setSortAsc] = useState(false);
  const [news, setNews] = useState([]);
  const [topFreeAgents, setTopFreeAgents] = useState([]);
  const [bidLoadingId, setBidLoadingId] = useState(null);
  const [bidMessage, setBidMessage] = useState('');
  const [leagueName, setLeagueName] = useState('');
  const leagueId = localStorage.getItem('fantasyLeagueId');

  const normalizeStandingRow = (row) => {
    const wins = Number(row?.wins ?? row?.overall_record?.wins ?? 0);
    const losses = Number(row?.losses ?? row?.overall_record?.losses ?? 0);
    const ties = Number(row?.ties ?? row?.overall_record?.ties ?? 0);
    const pf = Number(row?.pf ?? row?.points_for ?? row?.standings_metrics?.points_for ?? 0);
    const pa = Number(row?.pa ?? row?.points_against ?? row?.standings_metrics?.points_against ?? 0);
    const winPct = Number(
      row?.win_pct ??
        row?.overall_record?.win_pct ??
        row?.standings_metrics?.overall_record?.win_pct ??
        0
    );

    return {
      ...row,
      wins,
      losses,
      ties,
      pf,
      pa,
      win_pct: winPct,
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

  const displayRankReason = (owner) => {
    const reason = owner?.tiebreak_context?.rank_reason;
    if (!reason) return '-';
    return String(reason).replaceAll('_', ' ');
  };

  useEffect(() => {
    if (!leagueId) return;

    apiClient
      .get(`/leagues/${leagueId}`)
      .then((res) => setLeagueName(res.data.name))
      .catch(() => setLeagueName('League'));

    apiClient
      .get(`/leagues/owners?league_id=${leagueId}`)
      .then((res) => setStandings(Array.isArray(res.data) ? res.data : []))
      .catch(() => setStandings([]));

    apiClient
      .get(`/leagues/${leagueId}/news`)
      .then((res) => setNews(res.data))
      .catch(() => setNews([]));

    apiClient
      .get(`/players/top-free-agents?league_id=${leagueId}&limit=10`)
      .then((res) => setTopFreeAgents(Array.isArray(res.data) ? res.data : []))
      .catch(() => setTopFreeAgents([]));
  }, [leagueId]);

  const handleQuickBid = async (player) => {
    if (!player?.id) return;
    setBidMessage('');
    setBidLoadingId(player.id);
    try {
      await apiClient.post('/waivers/claim', {
        player_id: player.id,
        bid_amount: 0,
      });
      setTopFreeAgents((prev) => prev.filter((item) => item.id !== player.id));
      setBidMessage(`Claim submitted for ${player.name}.`);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setBidMessage(typeof detail === 'string' ? detail : 'Bid failed. Check waiver status and roster limits.');
    } finally {
      setBidLoadingId(null);
    }
  };

  return (
    <PageTemplate
      title={leagueName || 'League Dashboard'}
      subtitle={
        <>
          Welcome back, <span className="font-bold text-slate-900 dark:text-white">{username}</span>. Open the menu{' '}
          <span className="inline-block rounded bg-slate-200 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-700 dark:text-yellow-300">
            ☰
          </span>{' '}
          to access the War Room.
        </>
      }
      className="animate-fade-in"
    >

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className={`lg:col-span-2 ${cardSurface}`}>
          <div className="flex items-center gap-2 mb-4">
            <FiAward className="text-yellow-500" size={24} />
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">Current Standings</h2>
          </div>

          <StandardTableContainer>
            <StandardTable className="min-w-[760px]">
              <thead className={tableHead}>
                <tr>
                  <th className="px-4 py-3 min-w-[64px]">Rank</th>
                  <th className="px-4 py-3 cursor-pointer min-w-[160px]" onClick={() => handleSort('team_name')}>
                    Team{sortIndicator('team_name')}
                  </th>
                  <th className="px-4 py-3 min-w-[92px]">Div</th>
                  <th className="px-4 py-3 cursor-pointer min-w-[132px]" onClick={() => handleSort('username')}>
                    Owner{sortIndicator('username')}
                  </th>
                  <th className="px-4 py-3 cursor-pointer min-w-[96px]" onClick={() => handleSort('record')}>
                    W-L-T{sortIndicator('record')}
                  </th>
                  <th className="px-4 py-3 cursor-pointer min-w-[84px]" onClick={() => handleSort('pf')}>
                    PF{sortIndicator('pf')}
                  </th>
                  <th className="px-4 py-3 cursor-pointer min-w-[84px]" onClick={() => handleSort('pa')}>
                    PA{sortIndicator('pa')}
                  </th>
                  <th className="px-4 py-3 min-w-[124px]">TB Context</th>
                </tr>
              </thead>
              <tbody>
                {standings.length > 0 ? (
                  sortedStandings.map((owner, idx) => (
                    <StandardTableRow
                      key={owner.id}
                      className="border-b border-slate-300 dark:border-slate-800"
                    >
                      <td
                        className={`${tableCell} font-bold ${idx === 0 ? 'text-yellow-500' : 'text-slate-600 dark:text-slate-400'}`}
                      >
                        {idx + 1}
                      </td>
                      <td className={`${tableCell} font-medium text-slate-900 dark:text-white`}>
                        <Link to={`/team/${owner.id}`} className="hover:text-blue-400 transition-colors">
                          {owner.team_name || owner.username}
                        </Link>
                      </td>
                      <td className={tableCell}>
                        {owner.division_name ? (
                          <span className="rounded-md border border-slate-300 px-2 py-1 text-xs dark:border-slate-700">
                            {owner.division_name}
                          </span>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td className={tableCell}>
                        <Link to={`/team/${owner.id}`} className="hover:text-blue-400 transition-colors">
                          {owner.username}
                        </Link>
                      </td>
                      <td className={tableCell}>
                        {owner.wins}-{owner.losses}-{owner.ties}
                      </td>
                      <td className={tableCellNumeric}>{owner.pf}</td>
                      <td className={tableCellNumeric}>{owner.pa}</td>
                      <td className={`${tableCell} ${textCaption} capitalize`}>
                        {displayRankReason(owner)}
                      </td>
                    </StandardTableRow>
                  ))
                ) : (
                  <StandardTableStateRow colSpan={8}>
                    No owners found for this league.
                  </StandardTableStateRow>
                )}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        </div>

        <div className={cardSurface}>
          <div className="flex items-center gap-2 mb-4">
            <FiActivity className="text-blue-500" size={24} />
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">League News</h2>
          </div>
          <div className="space-y-3">
            {news.length > 0 ? (
              news.map((item, idx) => (
                <FeedPill
                  key={idx}
                  className={`w-full justify-between gap-3 ${item.type === 'info' ? 'border-l-2 border-green-500' : 'border-l-2 border-yellow-500'}`}
                >
                  <span className="text-slate-300 font-bold truncate">{item.title}</span>
                  <span className="text-slate-500 text-xs shrink-0">{item.timestamp}</span>
                </FeedPill>
              ))
            ) : (
              <div className="mt-4 text-center text-xs italic text-slate-500 dark:text-slate-400">End of feed</div>
            )}
          </div>
        </div>

        <div className={cardSurface}>
          <div className="flex items-center justify-between gap-2 mb-4">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">Hot Pickups</h2>
            <Link to="/waivers" className="text-xs text-cyan-600 dark:text-cyan-400 hover:underline">
              Full Waiver Wire
            </Link>
          </div>
          {bidMessage ? (
            <div className="mb-3 rounded border border-slate-300 dark:border-slate-700 px-2 py-1 text-xs text-slate-700 dark:text-slate-300">
              {bidMessage}
            </div>
          ) : null}
          <div className="space-y-2">
            {topFreeAgents.length > 0 ? (
              topFreeAgents.map((player, idx) => (
                <div
                  key={player.id}
                  className="flex items-center justify-between gap-2 rounded border border-slate-200 dark:border-slate-700 p-2"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">{idx + 1}. {player.name}</p>
                    <p className="text-xs text-slate-600 dark:text-slate-400">
                      {player.position} - {player.nfl_team || 'FA'} - ROS {Number(player.projected_points || 0).toFixed(1)}
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Score {Number(player.pickup_score || 0).toFixed(1)}
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Trend {player.pickup_trend_label || 'Steady'} ({Number(player.pickup_trend_score || 0).toFixed(1)})
                    </p>
                    {Number(player.recent_claim_count || 0) > 0 ? (
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        Claims {Number(player.recent_claim_count || 0)}
                      </p>
                    ) : null}
                  </div>
                  <div className="shrink-0 flex items-center gap-2">
                    <span className="rounded border border-cyan-500/40 bg-cyan-500/10 px-2 py-1 text-[10px] font-bold text-cyan-600 dark:text-cyan-300">
                      {player.pickup_tier || 'C'} Tier
                    </span>
                    <button
                      onClick={() => handleQuickBid(player)}
                      disabled={bidLoadingId === player.id}
                      className="shrink-0 rounded bg-cyan-600 px-2 py-1 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
                    >
                      {bidLoadingId === player.id ? 'Bidding...' : 'Bid'}
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState
                message="No free agents available for this league."
                className="text-xs italic"
              />
            )}
          </div>
        </div>
      </div>
    </PageTemplate>
  );
}
