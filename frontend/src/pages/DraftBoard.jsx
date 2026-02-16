import { useEffect, useState, useCallback, useMemo } from 'react';
import apiClient from '@api/client'; 
import { useDraftTimer } from '@hooks/useDraftTimer';
import { 
  getOwnerStats, 
  normalizePos, 
  ROSTER_SIZE 
} from '@utils';

import { 
  OwnerCard, 
  AuctionBlock, 
  SessionHeader, 
  DraftHistoryFeed 
} from '@components/draft';

export default function DraftBoard({ token, activeOwnerId }) {
  // --- STATE ---
  const [owners, setOwners] = useState([]);
  const [players, setPlayers] = useState([]); 
  const [winnerId, setWinnerId] = useState(activeOwnerId); 
  const [sessionId] = useState(`TEST_${new Date().toISOString().slice(0,10)}`);
  const [history, setHistory] = useState([]);
  const [playerName, setPlayerName] = useState('');
  const [bidAmount, setBidAmount] = useState(1);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [posFilter, setPosFilter] = useState('ALL');

  // --- 1. DATA LOADING ---
  const fetchHistory = useCallback(() => {
    apiClient.get(`/draft/history?session_id=${sessionId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => {
        setHistory(res.data);
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

  // --- 5. THE CLEAN RETURN ---
  return (
    <div className="bg-slate-950 min-h-screen">
      <div className="max-w-[1800px] mx-auto p-4 grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* LEFT: MAIN CONTENT (9 columns on large screens) */}
        <div className="lg:col-span-9 space-y-6">
          
          {/* STICKY AUCTION BLOCK */}
          <div className="sticky top-4 z-20 bg-slate-900 border-b border-yellow-600 shadow-2xl pb-6 px-6 pt-4 rounded-xl">
            <SessionHeader 
              sessionId={sessionId} 
              rosterSize={ROSTER_SIZE} 
              onFinalize={() => {}} 
            />
            <AuctionBlock 
              playerName={playerName}
              handleSearchChange={handleSearchChange}
              suggestions={suggestions}
              showSuggestions={showSuggestions}
              selectSuggestion={(p) => {setPlayerName(p.name); setShowSuggestions(false)}}
              posFilter={posFilter}
              setPosFilter={setPosFilter}
              winnerId={winnerId}
              setWinnerId={setWinnerId}
              owners={owners}
              activeStats={activeStats}
              bidAmount={bidAmount}
              setBidAmount={setBidAmount}
              handleDraft={handleDraft}
              timeLeft={timeLeft}
              isTimerRunning={isTimerRunning}
              reset={reset}
              start={start}
            />
          </div>

          {/* OWNER GRID */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {owners.map(owner => (
              <OwnerCard 
                key={owner.id} 
                owner={owner} 
                stats={getOwnerStats(owner.id, history, players)} 
                isNominator={owner.id === currentNominatorId} 
                isSelectedWinner={owner.id === winnerId}
                myPicks={history.filter(h => h.owner_id === owner.id)} 
                players={players} 
              />
            ))}
          </div>
        </div>

        {/* RIGHT: LIVE FEED (3 columns on large screens) */}
        <div className="lg:col-span-3">
          <div className="sticky top-4 h-[calc(100vh-2rem)]">
            <DraftHistoryFeed history={history} owners={owners} />
          </div>
        </div>

      </div>
    </div>
  );
}