// frontend/src/pages/SiteAdmin.jsx
import React, { useState } from 'react';
import axios from 'axios';
import { FiRefreshCw, FiTool, FiDatabase, FiCheckCircle, FiBox } from 'react-icons/fi';
import Toast from '../components/Toast'; 

export default function SiteAdmin({ token }) {
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [lastSync, setLastSync] = useState(null);

  // Helper to standardise toast calls
  const showToast = (message, type) => {
    setToast({ message, type });
  };

  // --- ACTION: RUN NFL SYNC ---
  const runSync = async () => {
    setLoading(true);
    try {
      const res = await axios.post('http://127.0.0.1:8000/admin/tools/sync-nfl', {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Use detail from backend if available, else generic success
      showToast(res.data.detail || "Sync Started! Players added.", 'success');
      setLastSync(new Date().toLocaleTimeString()); 
    } catch (err) {
      const errorMsg = err.response?.data?.detail || "Sync Failed";
      showToast(errorMsg, 'error');
    } finally {
      setLoading(false);
    }
  };

  // --- ACTION: CREATE TEST LEAGUE ---
  const runTestLeague = async () => {
    setLoading(true);
    try {
      const res = await axios.post('http://127.0.0.1:8000/admin/create-test-league', {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      showToast(res.data.message || "League Generated!", 'success');
    } catch (err) {
      showToast("Failed to create Test League", 'error');
    } finally {
      setLoading(false);
    }
  };
  // Add this to your SiteAdmin.jsx actions
  const resetDraft = async () => {
    if (!window.confirm("⚠️ DANGER: This will wipe all draft picks. Continue?")) return;
    setLoading(true);
    try {
      await axios.post('http://127.0.0.1:8000/admin/reset-draft', {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setLastSync("Draft Reset: " + new Date().toLocaleTimeString());
      setToast({ message: "Draft history purged!", type: 'success' });
    } catch (err) {
      setToast({ message: "Reset failed", type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto text-white min-h-screen">
      {/* Header */}
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

        {/* CARD 2: SANDBOX */}
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl hover:border-yellow-500/30 transition">
          <div className="flex justify-between items-start mb-4">
             <FiBox className="text-yellow-400 text-3xl" />
             <div className="bg-yellow-900/30 text-yellow-400 text-xs font-bold px-2 py-1 rounded">SANDBOX</div>
          </div>
          <h3 className="text-xl font-bold mb-2">Test League Gen</h3>
          <p className="text-slate-400 text-sm mb-6 min-h-[40px]">
            Create "Test League 2026" with 12 dummy owners for testing.
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
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
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
              <span className="text-slate-400">Last NFL Sync</span>
              <span className="text-white font-mono">{lastSync || 'Never'}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Environment</span>
              <span className="text-yellow-500 font-mono italic">Development</span>
            </div>
          </div>
        </div>
      </div>

      {/* Toast Notification */}
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