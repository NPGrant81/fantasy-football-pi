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

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };
  const [news, setNews] = useState([]);
  const [leagueName, setLeagueName] = useState('');
  const leagueId = localStorage.getItem('fantasyLeagueId');

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
  }, [leagueId]);
  // --- 1.1 CONFIGURATION ---
  // Note: This page currently serves as a static landing.
  // Future 1.2 Data Retrieval for "League News" will go here.

  return (
    <div className={`${pageShell} animate-fade-in`}>
      {/* 2.1 WELCOME BANNER */}
      <div className={`${pageHeader} border-b-0 pb-0`}>
        <h1 className={pageTitle}>
          {leagueName || 'League Dashboard'}
        </h1>
        <p className={pageSubtitle}>
          Welcome back, <span className="font-bold text-slate-900 dark:text-white">{username}</span>
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

          <div className={tableSurface}>
            <table className="w-full text-sm text-left text-slate-700 dark:text-slate-300">
              <thead className={tableHead}>
                <tr>
                  <th className="px-4 py-3">Rank</th>
                  <th
                    className="px-4 py-3 cursor-pointer"
                    onClick={() => handleSort('team_name')}
                  >
                    Team
                  </th>
                  <th
                    className="px-4 py-3 cursor-pointer"
                    onClick={() => handleSort('username')}
                  >
                    Owner
                  </th>
                  <th
                    className="px-4 py-3 cursor-pointer"
                    onClick={() => handleSort('wins')}
                  >
                    W-L-T
                  </th>
                  <th
                    className="px-4 py-3 cursor-pointer"
                    onClick={() => handleSort('pf')}
                  >
                    PF
                  </th>
                  <th
                    className="px-4 py-3 cursor-pointer"
                    onClick={() => handleSort('pa')}
                  >
                    PA
                  </th>
                </tr>
              </thead>
              <tbody>
                {standings.length > 0 ? (
                  <>
                    {/* apply sorting */}
                    {[...standings]
                      .sort((a, b) => {
                        let av = a[sortField] || 0;
                        let bv = b[sortField] || 0;
                        if (
                          sortField === 'team_name' ||
                          sortField === 'username'
                        ) {
                          av = av.toLowerCase();
                          bv = bv.toLowerCase();
                        }
                        if (av < bv) return sortAsc ? -1 : 1;
                        if (av > bv) return sortAsc ? 1 : -1;
                        return 0;
                      })
                      .map((owner, idx) => (
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
                          <td className="px-4 py-3">{owner.pf}</td>
                          <td className="px-4 py-3">{owner.pa}</td>
                        </tr>
                      ))}
                  </>
                ) : (
                  <tr>
                    <td colSpan={6} className="text-center py-6 text-slate-500 dark:text-slate-400">
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
      </div>
    </div>
  );
}
