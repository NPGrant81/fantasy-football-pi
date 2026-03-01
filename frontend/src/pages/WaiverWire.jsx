import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import GlobalSearch from '../components/GlobalSearch';
import apiClient from '@api/client';
import Toast from '@components/Toast';
import {
  WaiverTable,
  WaiverPositionTabs,
  DropPlayerModal,
} from '@components/waivers';
import {
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '../utils/uiStandards';

export default function WaiverWire({ ownerId, username, leagueName }) {
  const navigate = useNavigate();
  // --- 1.1 STATE MANAGEMENT ---
  const [players, setPlayers] = useState([]);
  const [myRoster, setMyRoster] = useState([]); // Needed for the Drop Modal
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState(null);
  const [activeTab, setActiveTab] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [waiverDeadline, setWaiverDeadline] = useState(null); // New state for waiver deadline
  const [draftStatus, setDraftStatus] = useState('PRE_DRAFT');
  const [rosterSizeLimit, setRosterSizeLimit] = useState(14);
  const [toast, setToast] = useState(null);
  // show back button when possible (history stack length > 1)
  const [showBack, setShowBack] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);

  // Modal State
  const [isDropModalOpen, setIsDropModalOpen] = useState(false);
  const [pendingPlayer, setPendingPlayer] = useState(null);

  const showToast = (message, type = 'info') => {
    setToast({ message, type });
  };

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
    // show back button if history has previous entry
    if (window.history.length > 1) setShowBack(true);

    if (ownerId) fetchWaivers();
    // Fetch waiver deadline from league settings
    const fetchWaiverDeadline = async () => {
      try {
        // Try to get leagueId from leagueName if possible, else skip
        // If leagueName is actually the league ID, use it directly
        if (leagueName) {
          const leagueRes = await apiClient.get(`/leagues/${leagueName}`);
          setDraftStatus(leagueRes.data?.draft_status || 'PRE_DRAFT');

          const res = await apiClient.get(`/leagues/${leagueName}/settings`);
          setWaiverDeadline(res.data.waiver_deadline);
          setRosterSizeLimit(res.data.roster_size || 14);
        }
      } catch {
        setWaiverDeadline(null);
        setDraftStatus('PRE_DRAFT');
        setRosterSizeLimit(14);
      }
    };
    fetchWaiverDeadline();
    // Timeout loading state after 10 seconds
    const timeout = setTimeout(() => {
      setLoading(false);
    }, 10000);
    return () => clearTimeout(timeout);
  }, [ownerId, fetchWaivers, leagueName]);

  // --- 2.1 ACTION: CLAIM PLAYER ---

  // --- 2.1 ACTION: CLAIM PLAYER ---
  const executeClaim = async (player) => {
    if (draftStatus === 'ACTIVE') {
      showToast('Waiver wire is locked while the draft is active.', 'error');
      return;
    }

    if (myRoster.length >= rosterSizeLimit) {
      setPendingPlayer(player);
      setIsDropModalOpen(true);
      showToast('Roster full. Choose a player to drop first.', 'info');
      return;
    }

    setProcessingId(player.id);
    try {
      // 2.1.1 Attempt the claim
      await apiClient.post('/waivers/claim', {
        player_id: player.id,
        bid_amount: 0,
      });

      // 2.1.2 Success: Update UI
      setPlayers((prev) => prev.filter((p) => p.id !== player.id));
      setMyRoster((prev) => [...prev, player]);
      showToast(`${player.name} added to your roster.`, 'success');
    } catch (err) {
      // 2.1.3 Handle "Roster Full" specifically
      if (err.response?.data?.detail?.includes('Roster full')) {
        setPendingPlayer(player);
        setIsDropModalOpen(true);
        showToast('Roster full. Choose a player to drop first.', 'info');
      } else {
        showToast(err.response?.data?.detail || 'Claim failed', 'error');
      }
    } finally {
      setProcessingId(null);
    }
  };

  const handleClaim = (player) => {
    setConfirmAction({
      kind: 'claim',
      message: `Claim ${player.name}?`,
      payload: { player },
    });
  };

  // --- 2.2 ACTION: DROP & ADD (The Swap) ---
  const executeDropAndAdd = async (playerToDropId) => {
    try {
      if (draftStatus === 'ACTIVE') {
        showToast('Waiver wire is locked while the draft is active.', 'error');
        return;
      }

      if (!pendingPlayer) {
        showToast('No pending waiver claim selected.', 'error');
        return;
      }

      // 2.2.1 Atomic swap: claim new player and drop old player in one request
      await apiClient.post('/waivers/claim', {
        player_id: pendingPlayer.id,
        bid_amount: 0,
        drop_player_id: playerToDropId,
      });

      showToast(
        `${pendingPlayer.name} added. Player dropped successfully.`,
        'success'
      );
      setPlayers((prev) =>
        prev.filter((player) => player.id !== pendingPlayer.id)
      );

      // 2.2.3 Close modal and refresh roster
      setIsDropModalOpen(false);
      setPendingPlayer(null);
      fetchWaivers();
    } catch (err) {
      showToast(
        'Swap failed: ' + (err.response?.data?.detail || 'Unknown error'),
        'error'
      );
    }
  };

  const handleDropAndAdd = (playerToDropId) => {
    const dropped = myRoster.find((player) => player.id === playerToDropId);
    setConfirmAction({
      kind: 'drop-and-add',
      message: `Drop ${dropped?.name || 'this player'} and add ${pendingPlayer?.name || 'new player'}?`,
      payload: { playerToDropId },
    });
  };

  const handleConfirmAction = async () => {
    if (!confirmAction) return;

    const action = confirmAction;
    setConfirmAction(null);

    if (action.kind === 'claim') {
      await executeClaim(action.payload.player);
      return;
    }

    if (action.kind === 'drop-and-add') {
      await executeDropAndAdd(action.payload.playerToDropId);
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
    <div className={pageShell}>
      {/* 2.3 UI: HEADER & SEARCH */}
      <div className={`${pageHeader} flex flex-col md:flex-row justify-between md:items-end gap-4`}>
        <div className="space-y-2">
          {showBack && (
            <button
              className={`${buttonSecondary} px-3 py-1.5 text-xs`}
              onClick={() => navigate(-1)}
            >
              ← Back
            </button>
          )}
          <h1 className={pageTitle}>Waiver Wire</h1>
          <p className={pageSubtitle}>Available free agents</p>
          <div className="text-sm text-slate-600 dark:text-slate-300">
            User:{' '}
            <span className="font-semibold text-slate-900 dark:text-white">
              {username || 'Unknown'}
            </span>{' '}
            |
            League:{' '}
            <span className="font-semibold text-slate-900 dark:text-white">
              {leagueName || 'Unknown'}
            </span>
            {waiverDeadline && (
              <div className="mt-1 text-xs text-cyan-600 dark:text-cyan-300">
                Waiver Deadline: {waiverDeadline}
              </div>
            )}
            <div className="mt-1 text-xs">
              <a
                href="/waiver-rules"
                className="underline text-cyan-600 hover:text-cyan-500 dark:text-cyan-400 dark:hover:text-cyan-300"
              >
                View waiver rules
              </a>
            </div>
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
      {draftStatus === 'ACTIVE' ? (
        <div
          className={`${cardSurface} border-orange-500/50 bg-orange-100/50 text-center dark:bg-orange-900/20`}
        >
          <h2 className="text-xl font-black tracking-tight text-orange-700 dark:text-orange-300">
            Waiver Wire Locked
          </h2>
          <p className="mt-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
            The draft is currently active. Waiver claims open when the draft is
            finalized.
          </p>
        </div>
      ) : (
        <>
          <WaiverPositionTabs
            activeTab={activeTab}
            setActiveTab={setActiveTab}
          />

          <div className="mt-8">
            <WaiverTable
              players={filteredPlayers}
              onClaim={handleClaim}
              processingId={processingId}
              loading={loading}
            />
          </div>
        </>
      )}

      {/* 2.5 UI: DROP MODAL (Hidden by default) */}
      <DropPlayerModal
        isOpen={isDropModalOpen}
        onClose={() => setIsDropModalOpen(false)}
        myRoster={myRoster}
        onConfirm={handleDropAndAdd}
      />

      {confirmAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-brand-black p-6 shadow-2xl">
            <h3 className="text-lg font-black tracking-tight text-white">
              Confirm Waiver Action
            </h3>
            <p className="mt-3 text-sm text-slate-300">
              {confirmAction.message}
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setConfirmAction(null)}
                className={buttonSecondary}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmAction}
                className={buttonPrimary}
              >
                Accept
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
