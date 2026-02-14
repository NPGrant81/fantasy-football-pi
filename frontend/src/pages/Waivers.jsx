// frontend/src/components/Waivers.jsx
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { getPosColor, normalizePos } from '../utils/draftHelpers';
import { FiPlusCircle, FiSearch } from 'react-icons/fi';

export default function Waivers({ token, activeOwnerId }) {
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Calling the salvaged endpoint from routers/players.py
    axios.get('http://127.0.0.1:8000/players/waiver-wire')
      .then(res => {
        setPlayers(res.data);
        setLoading(false);
      });
  }, []);

  const handleClaim = (player) => {
    const confirmAdd = window.confirm(`Submit waiver claim for ${player.name}?`);
    if (confirmAdd) {
      // Logic for the claim microservice will go here next!
      alert(`Claim submitted for ${player.name}. Check back Wednesday!`);
    }
  };

  if (loading) return <div className="p-20 text-center animate-pulse text-slate-500">Scanning the wire...</div>;

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-4xl font-black uppercase italic tracking-tighter text-white">Waiver Wire</h1>
        <div className="text-xs text-slate-500 font-mono bg-slate-900 border border-slate-800 px-3 py-1 rounded">
          Status: <span className="text-green-500">Open</span>
        </div>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-3xl overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-800/50 text-slate-500 text-[10px] uppercase tracking-widest">
              <th className="p-4">Player</th>
              <th className="p-4">Team</th>
              <th className="p-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {players.map(player => (
              <tr key={player.id} className="hover:bg-slate-800/30 transition group">
                <td className="p-4">
                  <div className="flex items-center gap-3">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${getPosColor(player.position)}`}>
                      {normalizePos(player.position)}
                    </span>
                    <span className="text-white font-bold">{player.name}</span>
                  </div>
                </td>
                <td className="p-4 text-slate-400 text-sm font-mono">{player.nfl_team}</td>
                <td className="p-4 text-right">
                  <button 
                    onClick={() => handleClaim(player)}
                    className="text-purple-500 hover:text-purple-400 transition transform group-hover:scale-110"
                  >
                    <FiPlusCircle size={24} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}