import { useEffect, useState, useCallback, useMemo } from 'react';
import apiClient from '../api/client'; 
import { useDraftTimer } from '../hooks/useDraftTimer';
import { getOwnerStats, normalizePos, POSITIONS, ROSTER_SIZE } from '../utils/draftHelpers';

import OwnerCard from "../components/OwnerCard";
import AuctionBlock from "../components/AuctionBlock";
import SessionHeader from "../components/SessionHeader";

export default function DraftBoard({ token, activeOwnerId }) {
  const [owners, setOwners] = useState([]);
  const [players, setPlayers] = useState([]); 
  const [winnerId, setWinnerId] = useState(activeOwnerId); 
  const [sessionId] = useState(`TEST_${new Date().toISOString().slice(0,10)}`);
  const [history, setHistory] = useState([]); // This stores who was drafted for what
  const [playerName, setPlayerName] = useState('');
  const [bidAmount, setBidAmount] = useState(1);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [posFilter, setPosFilter] = useState('ALL');

  // --- 1. FIXED DATA LOADING (Top Level) ---
  const fetchHistory = useCallback(() => {
    apiClient.get(`/draft/history?session_id=${sessionId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => {
        setHistory(res.data);
        // Sync search bar: if player was just drafted by someone else, clear our search
        const draftedIds = new Set(res.data.map(h => h.player_id));
        const currentP = players.find(p => p.name.toLowerCase() === playerName.toLowerCase());
        if (currentP && draftedIds.has(currentP.id)) {
          setPlayerName('');
          setSuggestions([]);
        }
      })
      .catch(() => console.log("No history yet"));
  }, [sessionId, token, players, playerName]);

  // --- 2. THE HEARTBEAT (Polling) ---
  useEffect(() => {
    if (token) {
      const config = { headers: { Authorization: `Bearer ${token}` }};
      apiClient.get('/league/owners', config).then(res => setOwners(res.data));
      apiClient.get('/players/', config).then(res => setPlayers(res.data));
      fetchHistory();

      const interval = setInterval(fetchHistory, 3000); 
      return () => clearInterval(interval);
    }
  }, [token, fetchHistory]);

  // --- 3. DRAFT ACTION ---
  const handleDraft = useCallback(async () => {
    if (!winnerId || !playerName) return;
    const foundPlayer = players.find(p => p.name.toLowerCase() === playerName.toLowerCase());
    if (!foundPlayer || history.some(h => h.player_id === foundPlayer.id)) return;

    const payload = {
      owner_id: winnerId,
      player_id: foundPlayer.id,
      amount: bidAmount,
      session_id: sessionId
    };

    try {
      await apiClient.post('/draft/pick', payload, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPlayerName('');
      setBidAmount(1);
      fetchHistory();
      reset(); 
    } catch (err) {
      alert("Draft failed! " + (err.response?.data?.detail || "Error"));
    }
  }, [winnerId, playerName, players, history, bidAmount, sessionId, fetchHistory, token]);

  const { timeLeft, start, reset, isActive: isTimerRunning } = useDraftTimer(10, handleDraft);

  // --- 4. SEARCH & CALCULATIONS ---
  const handleSearchChange = async (e) => {
    const val = e.target.value;
    setPlayerName(val);
    if (val.length > 1) {
      try {
        const res = await apiClient.get(`/players/search?q=${val}&pos=${posFilter}`);
        const draftedIds = new Set(history.map(h => h.player_id));
        const filtered = res.data.filter(p => !draftedIds.has(p.id));
        setSuggestions(filtered.slice(0, 8));
        setShowSuggestions(true);
      } catch (err) { console.error(err); }
    } else { setShowSuggestions(false); }
  };

  const currentNominatorId = useMemo(() => {
    if (owners.length === 0) return null;
    return [...owners].sort((a,b) => a.id - b.id)[history.length % owners.length].id;
  }, [owners, history.length]);

  const activeStats = useMemo(() => {
    return winnerId ? getOwnerStats(winnerId, history, players) : null;
  }, [winnerId, history, players]);

  return (
    <div className="p-4 bg-slate-950 min-h-screen flex flex-col lg:flex-row gap-6">
      
      {/* MAIN DRAFT AREA (Left/Middle) */}
      <div className="flex-grow">
        <div className="sticky top-0 z-20 bg-slate-900 border-b border-yellow-600 shadow-2xl pb-6 px-6 pt-4 rounded-b-xl">
          <SessionHeader sessionId={sessionId} rosterSize={ROSTER_SIZE} onFinalize={() => {}} />
          <AuctionBlock 
            {...{playerName, handleSearchChange, suggestions, showSuggestions, selectSuggestion: (p) => {setPlayerName(p.name); setShowSuggestions(false)}, 
            posFilter, setPosFilter, winnerId, setWinnerId, owners, activeStats, bidAmount, setBidAmount, handleDraft, timeLeft, isTimerRunning, reset, start}} 
          />
        </div>

        <div className="pt-8 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {owners.map(owner => (
            <OwnerCard key={owner.id} owner={owner} stats={getOwnerStats(owner.id, history, players)} 
            isNominator={owner.id === currentNominatorId} isSelectedWinner={owner.id === winnerId}
            myPicks={history.filter(h => h.owner_id === owner.id)} players={players} />
          ))}
        </div>
      </div>

      {/* --- LIVE ACTIVITY FEED (The "X drafted Y for $Z" part) --- */}
      <div className="w-full lg:w-80 bg-slate-900 border border-slate-800 rounded-2xl p-4 h-fit sticky top-4">
        <h2 className="text-yellow-500 font-black uppercase italic mb-4 border-b border-slate-800 pb-2">Recent Picks</h2>
        <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
          {[...history].reverse().map((pick, i) => {
            const owner = owners.find(o => o.id === pick.owner_id);
            return (
              <div key={i} className="bg-slate-950 p-3 rounded-lg border-l-4 border-yellow-500 animate-in slide-in-from-right duration-300">
                <div className="text-[10px] text-slate-500 font-bold uppercase">{new Date(pick.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
                <div className="text-white text-sm font-bold">
                  <span className="text-blue-400">{owner?.username || 'Owner'}</span> drafted
                </div>
                <div className="text-lg font-black text-yellow-500 uppercase italic leading-tight">
                  {pick.player_name}
                </div>
                <div className="text-xs font-mono text-green-400 font-bold">COST: ${pick.amount}</div>
              </div>
            );
          })}
          {history.length === 0 && <div className="text-slate-600 italic text-center py-10">Waiting for first pick...</div>}
        </div>
      </div>

    </div>
  );
}