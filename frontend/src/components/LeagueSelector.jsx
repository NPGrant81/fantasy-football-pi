import { useEffect, useState } from 'react';
import apiClient from '@api/client';
import { EmptyState, LoadingState } from '@components/common/AsyncState';

export default function LeagueSelector({ onLeagueSelect, _token }) {
  const [leagues, setLeagues] = useState([]);
  const [newLeagueName, setNewLeagueName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // --- 1. FETCH LEAGUES (Runs immediately) ---
  useEffect(() => {
    // FIX A: Removed "if (!_token) return" so it loads even if you aren't logged in yet.

    apiClient
      .get('/leagues/')
      .then((res) => {
        setLeagues(Array.isArray(res?.data) ? res.data : []);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Could not fetch leagues:', err);
        setError('Unable to load leagues right now.');
        setLoading(false);
      });
  }, []); // Dependency array is empty so it runs once on mount

  const handleSelect = async (leagueId) => {
    try {
      setError('');
      await apiClient.post('/leagues/join', null, {
        params: { league_id: leagueId },
      });
      onLeagueSelect(String(leagueId));
    } catch (err) {
      console.error('Could not join league:', err);
      setError('Unable to switch leagues. Please try again.');
    }
  };

  // --- 2. CREATE LEAGUE ---
  const handleCreate = () => {
    if (!newLeagueName) return;

    apiClient
      .post('/leagues/', { name: newLeagueName })
      .then((res) => {
        setLeagues([...leagues, res.data]);
        setNewLeagueName('');
        setIsCreating(false);
      })
      .catch(() => setError('Error creating league. Name might be taken.'));
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white">
      <div className="bg-slate-800 p-8 md:p-10 rounded-lg shadow-2xl w-full sm:max-w-md border border-slate-700">
        <h1 className="text-3xl font-black text-center text-yellow-500 mb-2">
          🏈 FANTASY WAR ROOM
        </h1>
        <p className="text-slate-400 text-center mb-8">
          Select your league to enter
        </p>
        {error ? (
          <p className="mb-4 text-center text-sm font-semibold text-red-300">
            {error}
          </p>
        ) : null}

        {/* LOADING STATE */}
        {loading ? (
          <LoadingState message="Loading leagues..." className="mb-6" />
        ) : (
          /* LIST OF LEAGUES */
          <div className="space-y-3 mb-6 max-h-60 overflow-y-auto custom-scrollbar">
            {leagues.map((league) => (
              <button
                key={league.id}
                onClick={() => handleSelect(league.id)}
                className="w-full text-left px-4 py-3 bg-slate-700 hover:bg-slate-600 rounded border border-slate-600 hover:border-yellow-500 transition-all flex justify-between group"
              >
                <span className="font-bold">{league.name}</span>
                <span className="text-slate-500 group-hover:text-yellow-400">
                  ENTER →
                </span>
              </button>
            ))}
            {leagues.length === 0 && (
              <EmptyState message="No leagues found. Create one!" />
            )}
          </div>
        )}

        {/* CREATE NEW TOGGLE */}
        {!isCreating ? (
          <button
            onClick={() => setIsCreating(true)}
            className="w-full py-2 text-slate-400 hover:text-white text-sm border-t border-slate-700 pt-4"
          >
            + Create New League
          </button>
        ) : (
          <div className="pt-4 border-t border-slate-700 animate-fade-in">
            <label className="text-xs font-bold text-slate-400 uppercase">
              New League Name
            </label>
            <div className="flex gap-2 mt-1">
              <input
                className="flex-grow bg-slate-900 border border-slate-600 rounded p-2 text-white outline-none focus:border-green-500"
                value={newLeagueName}
                onChange={(e) => setNewLeagueName(e.target.value)}
                placeholder="e.g. Dynasty 2026"
              />
              <button
                onClick={handleCreate}
                className="bg-green-600 hover:bg-green-500 px-4 rounded font-bold text-sm"
              >
                SAVE
              </button>
              <button
                onClick={() => setIsCreating(false)}
                className="text-slate-500 hover:text-white px-2"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
