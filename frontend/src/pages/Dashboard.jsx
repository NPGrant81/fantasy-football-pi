// frontend/src/pages/Dashboard.jsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiTrendingUp, FiRepeat, FiBell, FiPlus, FiList } from 'react-icons/fi';

// Professional Imports
import apiClient from '@api/client';
import { getPosColor, normalizePos } from '@utils/draftHelpers';
import { ChatInterface } from '@components/chat';

export default function Dashboard({ ownerId }) {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    if (!ownerId) return;

    // Using the centralized client instead of hardcoded localhost
    apiClient
      .get(`/dashboard/${ownerId}`)
      .then((res) => setSummary(res.data))
      .catch((err) => console.error('Dashboard fetch failed', err));
  }, [ownerId]);

  if (!summary)
    return (
      <div className="p-10 text-center animate-pulse text-slate-500 font-black uppercase">
        Loading your locker room...
      </div>
    );

  return (
    <div className="max-w-6xl mx-auto p-6 text-white min-h-screen">
      {/* HEADER SECTION */}
      <div className="flex justify-between items-end mb-12 border-b border-slate-800 pb-8">
        <div>
          <h1 className="text-6xl font-black italic uppercase tracking-tighter leading-none">
            Your Locker Room
          </h1>
          <p className="text-slate-400 mt-4 flex items-center gap-2">
            Current Standing:{' '}
            <span className="bg-purple-600 text-white px-3 py-1 rounded-lg font-black italic">
              #{summary.standing} Place
            </span>
          </p>
        </div>

        {/* STAT BOXES */}
        <div className="flex gap-4">
          <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl text-center min-w-[140px] shadow-2xl">
            <FiRepeat className="mx-auto mb-2 text-blue-400 text-2xl" />
            <div className="text-[10px] text-slate-500 uppercase font-black tracking-widest">
              Pending Trades
            </div>
            <div className="text-3xl font-black">{summary.pending_trades}</div>
          </div>
        </div>
      </div>

      {/* MAIN CONTENT GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
        {/* LEFT COLUMN: ROSTER (8 Cols) */}
        <div className="lg:col-span-8 bg-slate-900/40 border border-slate-800 rounded-[2.5rem] p-8 backdrop-blur-sm">
          <h2 className="text-2xl font-black uppercase italic mb-8 flex items-center gap-3 text-slate-200">
            <FiTrendingUp className="text-green-500" /> Active Roster
          </h2>
          <div className="grid grid-cols-1 gap-3">
            {summary.roster.map((player) => (
              <div
                key={player.id}
                className="flex justify-between items-center p-5 bg-slate-950/50 border border-slate-800/50 rounded-2xl hover:border-blue-500/50 hover:bg-slate-900/50 transition-all duration-300 group"
              >
                <div className="flex items-center gap-5">
                  <span
                    className={`text-[10px] font-black px-3 py-1.5 rounded-md shadow-lg ${getPosColor(player.position)}`}
                  >
                    {normalizePos(player.position)}
                  </span>
                  <span className="font-bold text-xl tracking-tight group-hover:text-blue-400 transition-colors">
                    {player.name}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-slate-500 font-mono text-sm font-bold uppercase tracking-widest bg-slate-900 px-3 py-1 rounded-lg border border-slate-800">
                    {player.nfl_team}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT COLUMN: SIDEBAR (4 Cols) */}
        <div className="lg:col-span-4 space-y-8">
          {/* WAIVER QUICK ACTION */}
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-[2.5rem] shadow-2xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-green-500/5 blur-[80px] group-hover:bg-green-500/10 transition-all"></div>
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-black uppercase italic flex items-center gap-2 text-green-400 tracking-tighter text-xl">
                <FiList /> Waiver Wire
              </h3>
              <span className="text-[10px] bg-green-900/30 text-green-400 px-3 py-1 rounded-full border border-green-800/50 font-black">
                PRIORITY #4
              </span>
            </div>
            <p className="text-sm text-slate-400 mb-8 leading-relaxed">
              The wire is hot. Browse available free agents to fortify your
              lineup before the next window.
            </p>
            <Link
              to="/waivers"
              className="flex items-center justify-center gap-3 w-full py-4 bg-green-600 hover:bg-green-500 text-black rounded-2xl font-black uppercase tracking-widest transition shadow-[0_10px_20px_rgba(22,163,74,0.2)] active:scale-95"
            >
              <FiPlus className="text-xl" /> Find Players
            </Link>
          </div>

          {/* LEAGUE ALERTS */}
          <div className="bg-slate-900/80 border border-slate-800 p-8 rounded-[2.5rem]">
            <h3 className="font-black uppercase italic mb-6 flex items-center gap-2 text-slate-200 tracking-tighter text-xl">
              <FiBell className="text-blue-400" /> Sit-Rep
            </h3>
            <ul className="space-y-6">
              <li className="relative pl-6">
                <div className="absolute left-0 top-1 w-1 h-10 bg-purple-500 rounded-full"></div>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-1">
                  Waiver Deadline
                </p>
                <p className="text-white font-black text-lg">
                  2d 14h REMAINING
                </p>
              </li>
              <li className="relative pl-6 opacity-60">
                <div className="absolute left-0 top-1 w-1 h-10 bg-blue-500 rounded-full"></div>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-1">
                  Draft Status
                </p>
                <p className="text-white font-black text-lg tracking-tight uppercase">
                  Draft Finalized
                </p>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
