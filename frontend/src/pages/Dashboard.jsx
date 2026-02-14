// frontend/src/pages/Dashboard.jsx
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { getPosColor, normalizePos } from '../utils/draftHelpers';
import { FiTrendingUp, FiRepeat, FiBell, FiPlus, FiList } from 'react-icons/fi';

export default function Dashboard({ ownerId }) {
  const [summary, setSummary] = useState(null);

// Inside Dashboard.jsx

  useEffect(() => {
    // 1. STOP if ownerId is missing
    if (!ownerId) return; 

    // 2. Otherwise, fetch normally
    axios.get(`http://localhost:8000/dashboard/${ownerId}`)
      .then(res => setSummary(res.data))
      .catch(err => console.error("Dashboard fetch failed", err));
  }, [ownerId]);

  if (!summary) return <div className="p-10 text-center animate-pulse">Loading your locker room...</div>;

  return (
    <div className="max-w-6xl mx-auto p-6 text-white">
      {/* HEADER SECTION */}
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-5xl font-black italic uppercase tracking-tighter">Your Locker Room</h1>
          <p className="text-slate-400 mt-2">
            Current Standing: <span className="text-purple-400 font-bold">{summary.standing} Place</span>
          </p>
        </div>
        <div className="flex gap-4">
          <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl text-center min-w-[120px]">
            <FiRepeat className="mx-auto mb-1 text-blue-400" />
            <div className="text-xs text-slate-500 uppercase font-bold">Trades</div>
            <div className="text-xl font-black">{summary.pending_trades}</div>
          </div>
        </div>
      </div>

      {/* MAIN CONTENT GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* LEFT COLUMN: ROSTER */}
        <div className="lg:col-span-2 bg-slate-900/50 border border-slate-800 rounded-3xl p-6">
          <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
            <FiTrendingUp className="text-green-500" /> Active Roster
          </h2>
          <div className="space-y-3">
            {summary.roster.map(player => (
              <div key={player.id} className="flex justify-between items-center p-4 bg-slate-800/40 border border-slate-700/50 rounded-2xl hover:border-slate-500 transition">
                <div className="flex items-center gap-4">
                  <span className={`text-xs font-bold px-2 py-1 rounded ${getPosColor(player.position)}`}>
                    {normalizePos(player.position)}
                  </span>
                  <span className="font-bold text-lg">{player.name}</span>
                </div>
                <span className="text-slate-500 font-mono text-sm uppercase">{player.nfl_team}</span>
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT COLUMN: SIDEBAR */}
        <div className="space-y-6">
          
          {/* WAIVER QUICK ACTION */}
          <div className="bg-slate-900 border border-slate-800 p-6 rounded-3xl shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold flex items-center gap-2 text-green-400">
                <FiList /> Waiver Status
              </h3>
              <span className="text-[10px] bg-green-900/30 text-green-400 px-2 py-0.5 rounded-full border border-green-800/50">
                Priority: #4
              </span>
            </div>
            <p className="text-sm text-slate-400 mb-6">
              The wire is hot. Browse free agents to improve your roster.
            </p>
            <Link 
              to="/waivers" 
              className="flex items-center justify-center gap-2 w-full py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-bold transition active:scale-95"
            >
              <FiPlus /> Browse Free Agents
            </Link>
          </div>

          {/* LEAGUE ALERTS */}
          <div className="bg-gradient-to-br from-purple-900/20 to-blue-900/20 border border-purple-500/20 p-6 rounded-3xl">
            <h3 className="font-bold mb-4 flex items-center gap-2 text-slate-200">
              <FiBell /> League Alerts
            </h3>
            <ul className="text-sm space-y-4 text-slate-300">
              <li className="border-l-2 border-purple-500 pl-3">Waivers process in <span className="text-white font-bold">2d 14h</span></li>
              <li className="border-l-2 border-blue-500 pl-3">New trade proposal from <span className="text-white font-bold">Admin</span></li>
            </ul>
          </div>

        </div> {/* End Sidebar */}
      </div> {/* End Main Grid */}
    </div> 
  );
}