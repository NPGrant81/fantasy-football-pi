// frontend/src/pages/SiteAdmin.jsx
import React, { useState } from 'react';
import {
  FiRefreshCw,
  FiTool,
  FiDatabase,
  FiCheckCircle,
  FiBox,
  FiTrash2,
} from 'react-icons/fi';

// 1.1 PROFESSIONAL IMPORTS
import apiClient from '@api/client';
import Toast from '@components/Toast';
import { ChatInterface } from '@components/chat';

export default function SiteAdmin() {
  // --- 1.2 STATE MANAGEMENT ---
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [lastSync, setLastSync] = useState(null);

  // --- 1.3 UTILITIES ---
  const showToast = (message, type) => {
    setToast({ message, type });
  };

  // --- 2.1 ADMINISTRATIVE ACTIONS (The Engine) ---

  // 2.1.1 ACTION: RUN NFL SYNC
  const runSync = async () => {
    setLoading(true);
    try {
      const res = await apiClient.post('/admin/tools/sync-nfl');
      showToast(res.data.detail || 'Sync Started! Players added.', 'success');
      setLastSync(new Date().toLocaleTimeString());
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Sync Failed';
      showToast(errorMsg, 'error');
    } finally {
      setLoading(false);
    }
  };

  // 2.1.2 ACTION: CREATE TEST LEAGUE
  const runTestLeague = async () => {
    setLoading(true);
    try {
      const res = await apiClient.post('/admin/create-test-league');
      showToast(res.data.message || 'League Generated!', 'success');
    } catch (err) {
      showToast('Failed to create Test League', 'error');
    } finally {
      setLoading(false);
    }
  };

  // 2.1.3 ACTION: RESET DRAFT (The Nuclear Option)
  const resetDraft = async () => {
    if (!window.confirm('⚠️ DANGER: This will wipe all draft picks. Continue?'))
      return;
    setLoading(true);
    try {
      await apiClient.post('/admin/reset-draft');
      setLastSync('Draft Reset: ' + new Date().toLocaleTimeString());
      showToast('Draft history purged!', 'success'); // Using utility function now
    } catch (err) {
      showToast('Reset failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  // --- 3.1 RENDER LOGIC (The View) ---
  return (
    <div className="p-8 max-w-6xl mx-auto text-white min-h-screen">
      {/* 3.2 HEADER */}
      <div className="flex items-center gap-4 mb-10 border-b border-slate-700 pb-6">
        <FiTool className="text-4xl text-purple-500" />
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Mission Control
          </h1>
          <p className="text-slate-400 text-sm">
            System status and administrative tools
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* CARD 1: DATA SYNC */}
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl hover:border-blue-500/30 transition">
          <div className="flex justify-between items-start mb-4">
            <FiDatabase className="text-blue-400 text-3xl" />
            <div className="bg-blue-900/30 text-blue-400 text-xs font-bold px-2 py-1 rounded">
              DATA
            </div>
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
            <div className="bg-yellow-900/30 text-yellow-400 text-xs font-bold px-2 py-1 rounded">
              SANDBOX
            </div>
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

        {/* CARD 3: RESET CONTROLS */}
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl hover:border-red-500/30 transition">
          <div className="flex justify-between items-start mb-4">
            <FiTrash2 className="text-red-400 text-3xl" />
            <div className="bg-red-900/30 text-red-400 text-xs font-bold px-2 py-1 rounded">
              DANGER
            </div>
          </div>
          <h3 className="text-xl font-bold mb-2">Reset Draft</h3>
          <p className="text-slate-400 text-sm mb-6 min-h-[40px]">
            Wipe all current draft picks and reset the board for a fresh start.
          </p>
          <button
            onClick={resetDraft}
            disabled={loading}
            className={`w-full py-3 rounded-xl font-black uppercase flex items-center justify-center gap-2 transition ${loading ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-red-600 hover:bg-red-500 text-white'}`}
          >
            <FiTrash2 />
            {loading ? 'Resetting...' : 'Reset Board'}
          </button>
        </div>
      </div>

      {/* 3.3 TOAST NOTIFICATION (FIXED SYNTAX) */}
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
