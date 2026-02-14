import { useEffect, useState, useCallback } from 'react'
import axios from 'axios'
import { useDraftTimer } from '../hooks/useDraftTimer';
import { getOwnerStats, normalizePos, POSITIONS, ROSTER_SIZE } from '../utils/draftHelpers';
import OwnerCard from './OwnerCard';
import AuctionBlock from './AuctionBlock';
import SessionHeader from './SessionHeader';

export default function DraftBoard({ token, activeOwnerId }) {
  // --- STATE ---
  const [owners, setOwners] = useState([])
  const [players, setPlayers] = useState([]) 
  const [winnerId, setWinnerId] = useState(activeOwnerId) 
  const [sessionId] = useState(`TEST_${new Date().toISOString().slice(0,10)}`)
  const [history, setHistory] = useState([])
  const [playerName, setPlayerName] = useState('')
  const [bidAmount, setBidAmount] = useState(1)
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [posFilter, setPosFilter] = useState('ALL')

  // --- DATA LOADING ---
  const fetchHistory = useCallback(() => {
    axios.get(`http://127.0.0.1:8000/draft-history?session_id=${sessionId}`)
      .then(res => setHistory(res.data))
      .catch(() => console.log("No history yet"))
  }, [sessionId]);

  useEffect(() => {
    if (token) {
      axios.get('http://127.0.0.1:8000/owners').then(res => setOwners(res.data))
      axios.get('http://127.0.0.1:8000/players').then(res => setPlayers(res.data))
      fetchHistory()
    }
  }, [token, sessionId, fetchHistory])

  // --- DRAFT ACTION ---
  const handleDraft = useCallback(() => {
    if (!winnerId || !playerName) return;
    
    const foundPlayer = players.find(p => p.name.toLowerCase() === playerName.toLowerCase())
    if (!foundPlayer || history.some(h => h.player_id === foundPlayer.id)) return;

    const payload = {
      owner_id: winnerId,
      player_id: foundPlayer.id,
      amount: bidAmount,
      session_id: sessionId
    }

    axios.post('http://127.0.0.1:8000/draft-pick', payload)
      .then(() => {
        setPlayerName('')
        setBidAmount(1)
        fetchHistory()
      })
      .catch(err => alert("Draft failed! " + (err.response?.data?.detail || "Error")));
  }, [winnerId, playerName, players, history, bidAmount, sessionId, fetchHistory])

  // --- TIMER HOOK ---
  const { timeLeft, start, reset, isActive: isTimerRunning } = useDraftTimer(10, handleDraft);

  // --- SEARCH LOGIC ---
  const handleSearchChange = async (e) => {
    const val = e.target.value
    setPlayerName(val)
    if (val.length > 1) {
      try {
        const res = await axios.get(`http://127.0.0.1:8000/players/search?q=${val}`)
        const draftedIds = new Set(history.map(h => h.player_id))
        const filtered = res.data.filter(p => {
          const notDrafted = !draftedIds.has(p.id)
          const posMatch = posFilter === 'ALL' || normalizePos(p.position) === posFilter
          return notDrafted && posMatch
        })
        setSuggestions(filtered.slice(0, 8))
        setShowSuggestions(true)
      } catch (err) { console.error(err) }
    } else { setShowSuggestions(false) }
  }

  const selectSuggestion = (player) => {
    setPlayerName(player.name)
    setShowSuggestions(false)
  }
  
  // --- LOGIC CALCULATIONS ---
  const currentNominatorId = owners.length > 0 
    ? [...owners].sort((a,b) => a.id - b.id)[history.length % owners.length].id 
    : null;

  const activeStats = winnerId ? getOwnerStats(winnerId, history, players) : null
// ADD THE FINALIZE LOGIC HERE
  const handleFinalize = useCallback(() => {
    if (!window.confirm("⚠️ End draft? This will lock all rosters and move the league to 'Live' mode.")) return;
    
    axios.post('http://127.0.0.1:8000/admin/finalize-draft')
      .then(res => {
         if (res.data.status === 'error') {
           alert("Cannot Finalize:\n" + res.data.messages.join("\n"));
         } else {
           alert("🎉 Draft Finalized!");
           window.location.href = "/";
         }
      });
  }, []);

  return (
    <div className="p-4 bg-slate-950 min-h-screen">
      {/* 1. TOP SECTION (Sticky Header) */}
      <div className="sticky top-0 z-20 bg-slate-900 border-b border-yellow-600 shadow-2xl pb-6 px-6 pt-4 rounded-b-xl">
        
        {/* MODULAR HEADER */}
                <SessionHeader 
                  sessionId={sessionId} 
                  rosterSize={ROSTER_SIZE} 
                  onFinalize={handleFinalize} 
                />

        {/* 2. THE AUCTION BLOCK (Modular Component) */}
        <AuctionBlock 
          playerName={playerName}
          handleSearchChange={handleSearchChange}
          suggestions={suggestions}
          showSuggestions={showSuggestions}
          selectSuggestion={selectSuggestion}
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

      {/* 3. THE OWNER GRID (Modular Cards) */}
      <div className="pt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
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
  );
}