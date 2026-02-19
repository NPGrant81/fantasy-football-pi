import React, { useEffect, useState, useCallback } from 'react';
import { FiSearch, FiRefreshCw } from 'react-icons/fi';
import GlobalSearch from '../components/GlobalSearch';
import apiClient from '@api/client';
import {
  WaiverTable,
  WaiverPositionTabs,
  DropPlayerModal,
} from '@components/waivers';
import { ChatInterface } from '@components/chat';

export default function WaiverWire({ token, ownerId, username, leagueName }) {
  // --- 1.1 STATE MANAGEMENT ---
  const [players, setPlayers] = useState([]);
  const [myRoster, setMyRoster] = useState([]); // Needed for the Drop Modal
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState(null);
  const [activeTab, setActiveTab] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [waiverDeadline, setWaiverDeadline] = useState(null); // New state for waiver deadline

  // Modal State
  const [isDropModalOpen, setIsDropModalOpen] = useState(false);
  const [pendingPlayer, setPendingPlayer] = useState(null);

  // --- 1.2 DATA FETCHING LOGIC ---
  const fetchWaivers = useCallback(async () => {
    setLoading(true);
    try {
      // 1.2.1 Get available free agents
      const res = await apiClient.get('/players/waiver-wire');
      setPlayers(res.data);

      // 1.2.2 Get current user's roster (to know who they can drop)
      const rosterRes = await apiClient.get(`/dashboard/${ownerId}`);
      setMyRoster(rosterRes.data.roster);
    } catch (err) {
      console.error('Fetch failed', err);
    } finally {
      setLoading(false);
    }
  }, [ownerId]);

  useEffect(() => {
    if (token && ownerId) fetchWaivers();
    // Fetch waiver deadline from league settings
    const fetchWaiverDeadline = async () => {
      try {
        // Try to get leagueId from leagueName if possible, else skip
        // If leagueName is actually the league ID, use it directly
        if (leagueName) {
          const res = await apiClient.get(`/leagues/${leagueName}/settings`);
          setWaiverDeadline(res.data.waiver_deadline);
        }
      } catch (err) {
        setWaiverDeadline(null);
      }
    };
    fetchWaiverDeadline();
    // Timeout loading state after 10 seconds
    const timeout = setTimeout(() => {
      setLoading(false);
    }, 10000);
    return () => clearTimeout(timeout);
  }, [token, ownerId, fetchWaivers, leagueName]);

  // --- 2.1 ACTION: CLAIM PLAYER ---
  const handleClaim = async (player) => {
    setProcessingId(player.id);
    try {
      // 2.1.1 Attempt the claim
      await apiClient.post('/waivers/claim', {
        player_id: player.id,
        bid_amount: 0,
      });

      // 2.1.2 Success: Update UI
      setPlayers((prev) => prev.filter((p) => p.id !== player.id));
      alert(`Success! ${player.name} added.`);
    } catch (err) {
      // 2.1.3 Handle "Roster Full" specifically
      if (err.response?.data?.detail?.includes('Roster full')) {
        setPendingPlayer(player);
        setIsDropModalOpen(true);
      } else {
        alert(err.response?.data?.detail || 'Claim failed');
      }
    } finally {
      setProcessingId(null);
    }
  };

  // --- 2.2 ACTION: DROP & ADD (The Swap) ---
  const handleDropAndAdd = async (playerToDropId) => {
    try {
      // 2.2.1 Drop the old player
      await apiClient.post('/waivers/drop', { player_id: playerToDropId });

      // 2.2.2 Immediately claim the new player
      {
        waiverDeadline && (
          <div className="mt-1 text-xs text-blue-300 font-mono">
            Waivers process every Wednesday at 10am ET
          </div>
        );
      }
      await handleClaim(pendingPlayer);

      // 2.2.3 Close modal and refresh roster
      setIsDropModalOpen(false);
      fetchWaivers();
    } catch (err) {
      alert('Swap failed: ' + (err.response?.data?.detail || 'Unknown error'));
    }
  };

  // --- 1.3 FILTERING ENGINE ---
  const filteredPlayers = players.filter((p) => {
    const matchesTab = activeTab === 'ALL' || p.position === activeTab;
    const matchesSearch = p.name
      .toLowerCase()
      .includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* 2.3 UI: HEADER & SEARCH */}
      <div className="flex flex-col md:flex-row justify-between items-end mb-10 gap-6">
        <div>
          <h1 className="text-6xl font-black uppercase italic tracking-tighter text-white leading-none">
            Waiver Wire
          </h1>
          <p className="text-slate-500 mt-4 font-bold text-xs tracking-[0.2em]">
            AVAILABLE FREE AGENTS
          </p>
          <div className="mt-2 text-slate-400 text-sm font-bold">
            User: <span className="text-white">{username || 'Unknown'}</span> |
            League:{' '}
            <span className="text-yellow-400">{leagueName || 'Unknown'}</span>
            {waiverDeadline && (
              <div className="mt-1 text-xs text-blue-300 font-mono">
                Waiver Deadline: {waiverDeadline}
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-4 w-full md:w-auto">
          <GlobalSearch
            onPlayerSelect={(player) => {
              setSearchQuery(player.name);
              setActiveTab(player.position);
            }}
          />
        </div>
      </div>

      {/* 2.4 UI: TABS & TABLE */}
      <WaiverPositionTabs activeTab={activeTab} setActiveTab={setActiveTab} />

      <div className="mt-8">
        <WaiverTable
          players={filteredPlayers}
          onClaim={handleClaim}
          processingId={processingId}
        />
      </div>

      {/* 2.5 UI: DROP MODAL (Hidden by default) */}
      <DropPlayerModal
        isOpen={isDropModalOpen}
        onClose={() => setIsDropModalOpen(false)}
        myRoster={myRoster}
        onConfirm={handleDropAndAdd}
      />
    </div>
  );
}
