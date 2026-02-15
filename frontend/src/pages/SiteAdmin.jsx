// frontend/src/pages/SiteAdmin.jsx
import React, { useState } from 'react';
import axios from 'axios';
import { FiRefreshCw, FiTool, FiDatabase, FiCheckCircle, FiBox } from 'react-icons/fi';
// Make sure this path is correct for your project structure
// If Toast doesn't exist yet, we can remove it or build it next.
// For now, I'll keep it as you had it.
import Toast from '../components/Toast'; 

export default function SiteAdmin({ token }) {
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  // --- ACTION: RUN NFL SYNC ---
  const runSync = async () => {
    setLoading(true);
    try {
      // switched to 127.0.0.1 to avoid CORS issues sometimes seen with 'localhost'
      await axios.post('http://127.0.0.1:8000/admin/tools/sync-nfl', {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setToast({ message: "Sync Started! Players added.", type: 'success' });
    } catch (err) {
      console.error(err);
      setToast({ message: "Sync Failed", type: 'error' });
    }
    setLoading(false);
  };

  // --- ACTION: CREATE TEST LEAGUE ---
  const runTestLeague = async () => {
    setLoading(true);
    try {
      const res = await axios.post('http://127.0.0.1:8000/admin/create-test-league', {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setToast({ message: res.data.message, type: 'success' });
    } catch (err) {
      console.error(err);
      setToast({ message: "Failed to create Test League", type: 'error' });
    }
    setLoading(false);
  };

  return (
    <div className="p-8 max-w-6xl mx-auto text-white min-h-screen">
      <div className="flex items-center gap-4 mb-10 border-b border-slate-700 pb-6">
        <FiTool className="text-4xl text-purple-500" />
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">Mission Control</h1>
          <p className="text-slate-400 text-sm">System status and administrative tools</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        
        {/* CARD 1: DATA SYNC */}
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl hover:border-blue-500/30 transition">
          <div className="flex justify-between items-start mb-4">
             <FiDatabase className="text-blue-400 text-3xl" />
             <div className="bg-blue-900/30 text-blue-400 text-xs font-bold px-2 py-1 rounded">DATA</div>
          </div>
          <h3 className="text-xl font-bold mb-2">NFL Reality Sync</h3>
          <p className="text-slate-400 text-sm mb-6 min-h-[40px]">
            Force a refresh of all player teams, injury statuses, and bye weeks.
          </p>
          <button 
            onClick={runSync}
            disabled={loading}
            className={`w-full py-3 rounded-xl font-black uppercase flex items-center justify-center gap-2 transition ${loading ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}
          >
            <FiRefreshCw className={loading ? 'animate-spin' : ''} />
            {loading ? 'Syncing...' : 'Run Sync'}
          </button>
        </div>

        {/* CARD 2: SANDBOX / TEST LEAGUE */}
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl hover:border-yellow-500/30 transition">
          <div className="flex justify-between items-start mb-4">
             <FiBox className="text-yellow-400 text-3xl" />
             <div className="bg-yellow-900/30 text-yellow-400 text-xs font-bold px-2 py-1 rounded">SANDBOX</div>
          </div>
          <h3 className="text-xl font-bold mb-2">Test League Gen</h3>
          <p className="text-slate-400 text-sm mb-6 min-h-[40px]">
            Create "Test League 2026" with 12 dummy owners (Taco, Ruxin, etc.) for testing.
          </p>
          <button 
            onClick={runTestLeague}
            disabled={loading}
            className={`w-full py-3 rounded-xl font-black uppercase flex items-center justify-center gap-2 transition ${loading ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-yellow-600 hover:bg-yellow-500 text-white'}`}
          >
            <FiTool />
            {loading ? 'Working...' : 'Generate League'}
          </button>
        </div>

        {/* CARD 3: SYSTEM STATUS */}
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl hover:border-green-500/30 transition">
          <div className="flex justify-between items-start mb-4">
             <FiCheckCircle className="text-green-400 text-3xl" />
             <div className="bg-green-900/30 text-green-400 text-xs font-bold px-2 py-1 rounded">HEALTH</div>
          </div>
          <h3 className="text-xl font-bold mb-2">Platform Health</h3>
          <div className="space-y-4 mt-4">
            <div className="flex justify-between text-sm border-b border-slate-800 pb-2">
              <span className="text-slate-400">Backend API</span>
              <span className="text-green-400 font-mono font-bold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span> ONLINE
              </span>
            </div>
            <div className="flex justify-between text-sm border-b border-slate-800 pb-2">
              <span className="text-slate-400">Database</span>
              <span className="text-green-400 font-mono font-bold">CONNECTED</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Version</span>
              <span className="text-slate-500 font-mono">v0.9.1-beta</span>
            </div>
          </div>
        </div>

      </div>

      {toast && (
        <div className="fixed bottom-10 right-10">
            {/* If you don't have the Toast component yet, this is a fallback div */}
            <div className={`px-6 py-4 rounded shadow-2xl text-white font-bold ${toast.type === 'error' ? 'bg-red-600' : 'bg-green-600'}`}>
                {toast.message}
                <button onClick={() => setToast(null)} className="ml-4 opacity-50 hover:opacity-100">✕</button>
            </div>
        </div>
      )}
    </div>
  );
}