// frontend/src/pages/Home.jsx
import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';
import { Link } from 'react-router-dom';
import FeedPill from '../../components/feeds/FeedPill';
import { FiAward, FiActivity, FiBarChart2 } from 'react-icons/fi';

export default function Home({ username }) {
  const [standings, setStandings] = useState([]);
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
    <div className="space-y-6 animate-fade-in">
      {/* 2.1 WELCOME BANNER */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6 shadow-lg">
        <h1 className="text-3xl font-black text-white italic tracking-tighter">
          {leagueName ? leagueName.toUpperCase() : 'LEAGUE DASHBOARD'}
        </h1>
        <p className="text-slate-400 mt-1">
          Welcome back, <span className="text-white font-bold">{username}</span>
          . Open the menu{' '}
          <span className="inline-block bg-slate-700 px-2 py-0.5 rounded text-xs text-yellow-400">
            ☰
          </span>{' '}
          to access the War Room.
        </p>
      </div>

      <Link
        to="/analytics"
        className="block bg-slate-900/50 border border-slate-800 rounded-xl p-4 shadow-xl hover:border-blue-500/60 transition"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-900/20 border border-blue-900/50">
              <FiBarChart2 className="text-blue-400" size={18} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                League Insights
              </h2>
              <p className="text-xs text-slate-400">
                View analytics charts and performance trends
              </p>
            </div>
          </div>
          <span className="text-xs font-bold text-blue-400 uppercase">
            Open
          </span>
        </div>
      </Link>

      {/* 2.2 STANDINGS & ACTIVITY GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 2.2.1 STANDINGS MODULE */}
        <div className="lg:col-span-2 bg-slate-900/50 border border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <FiAward className="text-yellow-500" size={24} />
            <h2 className="text-lg font-bold text-white uppercase tracking-widest">
              Current Standings
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left text-slate-400">
              <thead className="text-xs text-slate-500 uppercase bg-slate-950/50">
                <tr>
                  <th className="px-4 py-3">Rank</th>
                  <th className="px-4 py-3">Team</th>
                  <th className="px-4 py-3">Owner</th>
                </tr>
              </thead>
              <tbody>
                {standings.length > 0 ? (
                  standings.map((owner, idx) => (
                    <tr
                      key={owner.id}
                      className="border-b border-slate-800 hover:bg-slate-800/50"
                    >
                      <td
                        className={`px-4 py-3 font-bold ${idx === 0 ? 'text-yellow-500' : 'text-slate-400'}`}
                      >
                        {idx + 1}
                      </td>
                      <td className="px-4 py-3 font-medium text-white">
                        {owner.team_name || owner.username}
                      </td>
                      <td className="px-4 py-3">{owner.username}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3} className="text-center py-6 text-slate-500">
                      No owners found for this league.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* 2.2.2 RECENT ACTIVITY MODULE */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <FiActivity className="text-blue-500" size={24} />
            <h2 className="text-lg font-bold text-white uppercase tracking-widest">
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
              <div className="text-center text-xs text-slate-600 mt-4 italic">
                End of feed
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
