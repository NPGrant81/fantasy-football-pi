import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { FiPlusCircle, FiSearch, FiRefreshCw } from 'react-icons/fi';

export default function Waivers({ token, activeOwnerId }) {
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(null); // Track which player is being added

  useEffect(() => {
    fetchWaivers();
  }, [token]);

  const fetchWaivers = () => {
    setLoading(true);
    axios.get('http://127.0.0.1:8000/players/waiver-wire', {
        headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => {
        setPlayers(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  };

  const handleClaim = async (player) => {
    if (!window.confirm(`Add ${player.name} to your roster?`)) return;

    setProcessing(player.id);

    try {
        // --- THE REAL API CALL ---
        await axios.post('http://127.0.0.1:8000/waivers/claim', 
            { player_id: player.id, bid_amount: 0 },
            { headers: { Authorization: `Bearer ${token}` } }
        );

        // Success! Remove player from list immediately (Optimistic UI)
        setPlayers(players.filter(p => p.id !== player.id));
        alert(`${player.name} added to your team!`);

    } catch (err) {
        alert(err.response?.data?.detail || "Claim failed");
    }
    setProcessing(null);
  };

  if (loading) return <div className="p-20 text-center animate-pulse text-slate-500">Scanning the wire...</div>;

  return (
    <div className="max-w-5xl mx-auto p-4 md:p-8">
      <div className="flex justify-between items-center mb-8 border-b border-slate-700 pb-6">
        <div>
            <h1 className="text-4xl font-black uppercase italic tracking-tighter text-white">Waiver Wire</h1>
            <p className="text-slate-400 text-sm">Top available free agents</p>
        </div>
        <button onClick={fetchWaivers} className="text-slate-400 hover:text-white transition">
            <FiRefreshCw />
        </button>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-800 text-slate-400 text-[10px] uppercase tracking-widest">
              <th className="p-4">Pos</th>
              <th className="p-4">Player</th>
              <th className="p-4">NFL Team</th>
              <th className="p-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {players.length === 0 ? (
                <tr><td colSpan="4" className="p-8 text-center text-slate-500">No players found on waivers.</td></tr>
            ) : (
                players.map(player => (
                <tr key={player.id} className="hover:bg-slate-800/50 transition group">
                    <td className="p-4">
                        <span className={`text-[10px] font-bold px-2 py-1 rounded border ${getPosColor(player.position)}`}>
                            {player.position}
                        </span>
                    </td>
                    <td className="p-4 font-bold text-white text-lg">{player.name}</td>
                    <td className="p-4 text-slate-400 font-mono text-sm">{player.nfl_team}</td>
                    <td className="p-4 text-right">
                    <button 
                        onClick={() => handleClaim(player)}
                        disabled={processing === player.id}
                        className="text-green-500 hover:text-green-400 transition transform hover:scale-110 disabled:opacity-50"
                    >
                        {processing === player.id ? <FiRefreshCw className="animate-spin" /> : <FiPlusCircle size={28} />}
                    </button>
                    </td>
                </tr>
                ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --- HELPERS (Inlined to prevent crashes) ---
const getPosColor = (pos) => {
    switch (pos) {
        case 'QB': return 'bg-pink-900/30 text-pink-400 border-pink-700';
        case 'RB': return 'bg-green-900/30 text-green-400 border-green-700';
        case 'WR': return 'bg-blue-900/30 text-blue-400 border-blue-700';
        case 'TE': return 'bg-orange-900/30 text-orange-400 border-orange-700';
        default: return 'bg-slate-700 text-slate-300 border-slate-600';
    }
};