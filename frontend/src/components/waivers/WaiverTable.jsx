// src/pages/WaiverWire.jsx
import React, { useEffect, useState, useCallback } from 'react';
import { FiSearch, FiRefreshCw } from 'react-icons/fi';
import apiClient from '@api/client';
import { WaiverTable, WaiverPositionTabs } from '@components/waivers';

export default function WaiverWire({ token }) {
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState(null);
  const [activeTab, setActiveTab] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // --- SALVAGED LOGIC: FETCHING ---
  const fetchWaivers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/players/waiver-wire', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPlayers(res.data);
    } catch (err) {
      console.error('Failed to fetch waivers', err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) fetchWaivers();
  }, [token, fetchWaivers]);

  // --- SALVAGED LOGIC: CLAIMING ---
  const handleClaim = async (player) => {
    if (!window.confirm(`Add ${player.name} to your roster?`)) return;

    setProcessingId(player.id);
    try {
      await apiClient.post(
        '/waivers/claim',
        { player_id: player.id, bid_amount: 0 },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // OPTIMISTIC UI: Remove from local state immediately
      setPlayers((prev) => prev.filter((p) => p.id !== player.id));
      alert(`🎉 ${player.name} successfully claimed!`);
    } catch (err) {
      alert(err.response?.data?.detail || 'Claim failed');
    } finally {
      setProcessingId(null);
    }
  };

  // --- FILTERING LOGIC ---
  const filteredPlayers = players.filter((p) => {
    const matchesTab = activeTab === 'ALL' || p.position === activeTab;
    const matchesSearch = p.name
      .toLowerCase()
      .includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  if (loading)
    return (
      <div className="p-20 text-center animate-pulse text-slate-500 font-black uppercase tracking-widest">
        Scanning the wire...
      </div>
    );

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* HEADER SECTION */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-10 gap-6">
        <div>
          <h1 className="text-6xl font-black uppercase italic tracking-tighter text-white">
            Waiver Wire
          </h1>
          <p className="text-slate-400 mt-2 font-bold uppercase text-xs tracking-widest">
            Available Free Agents • Season 2026
          </p>
        </div>

        <div className="flex items-center gap-4 w-full md:w-auto">
          <div className="relative flex-grow md:w-64">
            <FiSearch className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Search Free Agents..."
              className="w-full bg-slate-900 border border-slate-800 rounded-2xl py-3 pl-12 pr-4 text-white focus:border-yellow-500 outline-none transition"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button
            onClick={fetchWaivers}
            className="p-4 bg-slate-900 border border-slate-800 rounded-2xl text-slate-400 hover:text-white transition active:scale-95"
          >
            <FiRefreshCw className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* TABS COMPONENT */}
      <WaiverPositionTabs activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* TABLE COMPONENT */}
      <div className="mt-6">
        <WaiverTable
          players={filteredPlayers}
          onClaim={handleClaim}
          processingId={processingId}
        />
      </div>
    </div>
  );
}
