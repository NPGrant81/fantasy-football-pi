import { useEffect, useState, useCallback, useMemo } from 'react';
import apiClient from '@api/client';
import { useDraftTimer } from '@hooks/useDraftTimer';
import { getOwnerStats, normalizePos, ROSTER_SIZE } from '@utils';
import {
  OwnerCard,
  AuctionBlock,
  SessionHeader,
  DraftHistoryFeed,
} from '@components/draft';
// import { ROSTER_SIZE } from '@utils/constants';
import { ChatInterface } from '@components/chat';

export default function DraftBoard({ token, activeOwnerId, activeLeagueId }) {
  // --- 1.1 STATE MANAGEMENT ---
  const [owners, setOwners] = useState([]);
  const [players, setPlayers] = useState([]);
  const [winnerId, setWinnerId] = useState(activeOwnerId);
  // Use league/session from props or localStorage
  const [sessionId] = useState(() => {
    const stored = localStorage.getItem('draftSessionId');
    if (stored) return stored;
    // fallback: league-based session or date
    if (activeLeagueId) return `LEAGUE_${activeLeagueId}`;
    return `TEST_${new Date().toISOString().slice(0, 10)}`;
  });
  const [leagueName, setLeagueName] = useState('');
  const [isCommissioner, setIsCommissioner] = useState(false);
  const [username, setUsername] = useState('');
  const [history, setHistory] = useState([]);
  const [playerName, setPlayerName] = useState('');
  const [bidAmount, setBidAmount] = useState(1);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [posFilter, setPosFilter] = useState('ALL');

  // --- 1.2 THE ENGINE (Logic Actions) ---

  const fetchHistory = useCallback(() => {
    apiClient
      .get(`/draft/history?session_id=${sessionId}`)
      .then((res) => setHistory(res.data))
      .catch(() => console.log('No history yet'));
  }, [sessionId]);

  // 1.2.1 THE DRAFT ACTION
  // We define this first, but we remove the 'reset' dependency.
  // The timer will now handle its own reset when handleDraft is triggered by the clock.
  const handleDraft = useCallback(async () => {
    if (!winnerId || !playerName) return;
    const foundPlayer = players.find(
      (p) => p.name.toLowerCase() === playerName.toLowerCase()
    );
    if (!foundPlayer || history.some((h) => h.player_id === foundPlayer.id))
      return;

    const payload = {
      owner_id: winnerId,
      player_id: foundPlayer.id,
      amount: bidAmount,
      session_id: sessionId,
    };

    try {
      await apiClient.post('/draft/pick', payload);
      setPlayerName('');
      setBidAmount(1);
      fetchHistory();
      // NOTE: We don't call reset() here anymore because the hook triggers it
      // when the button is clicked or time is up.
    } catch (err) {
      alert('Draft failed! ' + (err.response?.data?.detail || 'Error'));
    }
  }, [
    winnerId,
    playerName,
    players,
    history,
    bidAmount,
    sessionId,
    fetchHistory,
  ]);

  // 1.2.2 THE TIMER HOOK
  // Now that handleDraft is defined, we pass it in.
  const {
    timeLeft,
    start,
    reset,
    isActive: isTimerRunning,
  } = useDraftTimer(10, handleDraft);

  // --- 1.3 SEARCH & POLL ---

  const handleSearchChange = async (e) => {
    const val = e.target.value;
    setPlayerName(val);
    if (val.length > 1) {
      try {
        const res = await apiClient.get(
          `/players/search?q=${val}&pos=${posFilter}`
        );
        const draftedIds = new Set(history.map((h) => h.player_id));
        const filtered = res.data.filter((p) => !draftedIds.has(p.id));
        setSuggestions(filtered.slice(0, 8));
        setShowSuggestions(true);
      } catch (err) {
        console.error(err);
      }
    } else {
      setShowSuggestions(false);
    }
  };

  useEffect(() => {
    if (token && activeLeagueId) {
      apiClient.get(`/leagues/owners?league_id=${activeLeagueId}`).then((res) => setOwners(res.data));
      apiClient.get('/players/').then((res) => setPlayers(res.data));
      fetchHistory();
      // Fetch league name and user info
      apiClient.get(`/leagues/${activeLeagueId}`).then((res) => setLeagueName(res.data.name)).catch(() => setLeagueName('League'));
      apiClient.get('/auth/me').then((res) => {
        setIsCommissioner(res.data.is_commissioner);
        setUsername(res.data.username);
      }).catch(() => {
        setIsCommissioner(false);
        setUsername('');
      });
      const interval = setInterval(fetchHistory, 3000);
      return () => clearInterval(interval);
    }
  }, [token, activeLeagueId, fetchHistory]);

  // --- 1.4 DERIVED CALCULATIONS ---
  const currentNominatorId = useMemo(() => {
    if (owners.length === 0) return null;
    return [...owners].sort((a, b) => a.id - b.id)[
      history.length % owners.length
    ].id;
  }, [owners, history.length]);

  const activeStats = useMemo(() => {
    return winnerId ? getOwnerStats(winnerId, history, players) : null;
  }, [winnerId, history, players]);

  // --- 2.1 RENDER ---
  return (
    <div className="bg-slate-950 min-h-screen">
      <div className="max-w-[1800px] mx-auto p-4 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* USER/LEAGUE CONTEXT */}
        <div className="mb-4 text-xs text-slate-400">
          <span>User: <span className="font-bold text-blue-300">{username || '...'}</span></span>
          <span className="ml-4">League: <span className="font-bold text-yellow-400">{leagueName || '...'}</span></span>
        </div>
        {/* LEFT COLUMN */}
        <div className="lg:col-span-9 space-y-6">
          <div className="sticky top-4 z-20 bg-slate-900 border-b border-yellow-600 shadow-2xl pb-6 px-6 pt-4 rounded-xl">
            <SessionHeader
              sessionId={sessionId}
              rosterSize={ROSTER_SIZE}
              leagueName={leagueName}
              isCommissioner={isCommissioner}
              leagueId={activeLeagueId}
              onFinalize={() => {}}
            />
            <AuctionBlock
              playerName={playerName}
              handleSearchChange={handleSearchChange}
              suggestions={suggestions}
              showSuggestions={showSuggestions}
              selectSuggestion={(p) => {
                setPlayerName(p.name);
                setShowSuggestions(false);
              }}
              posFilter={posFilter}
              setPosFilter={setPosFilter}
              winnerId={winnerId}
              setWinnerId={setWinnerId}
              owners={owners}
              activeStats={activeStats}
              bidAmount={bidAmount}
              setBidAmount={setBidAmount}
              handleDraft={() => {
                handleDraft();
                reset();
              }} // RESET CALLED HERE ON MANUAL CLICK
              timeLeft={timeLeft}
              isTimerRunning={isTimerRunning}
              reset={reset}
              start={start}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {owners.length > 0 ? (
              owners.map((owner) => (
                <OwnerCard
                  key={owner.id}
                  owner={owner}
                  stats={getOwnerStats(owner.id, history, players)}
                  isNominator={owner.id === currentNominatorId}
                  isSelectedWinner={owner.id === winnerId}
                  myPicks={history.filter((h) => h.owner_id === owner.id)}
                  players={players}
                />
              ))
            ) : (
              <div className="col-span-full text-center text-slate-500 py-10 text-lg font-bold">No owners found for this league.</div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div className="lg:col-span-3">
          <div className="sticky top-4 h-[calc(100vh-2rem)]">
            {/* DraftHistoryFeed moved to ticker at bottom */}
          </div>
        </div>
      </div>
      {/* Horizontal Draft Ticker */}
      <DraftHistoryFeed history={history} owners={owners} />
    </div>
  );
}
