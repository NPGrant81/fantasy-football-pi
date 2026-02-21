import React, { useState } from 'react';
import {
  FiRefreshCw,
  FiTool,
  FiDatabase,
  FiBox,
  FiTrash2,
  FiUsers,
} from 'react-icons/fi';
import apiClient from '@api/client';
import Toast from '@components/Toast';

export default function SiteAdmin() {
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [lastSync, setLastSync] = useState(null);

  const showToast = (message, type) => {
    setToast({ message, type });
  };

  // GOD-LEVEL ADMIN ACTIONS
  const runSync = async () => {
    setLoading(true);
    try {
      // Sync can take 2+ minutes with ESPN API calls, so use longer timeout
      const res = await apiClient.post('/admin/tools/sync-nfl', {}, { timeout: 300000 });
      showToast(res.data.detail || 'Sync Started! Players added.', 'success');
      setLastSync(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Sync error:', err);
      const errorMsg = 
        err.response?.data?.detail || 
        err.response?.statusText || 
        err.message || 
        'Sync Failed - Check console for details';
      showToast(errorMsg, 'error');
    } finally {
      setLoading(false);
    }
  };

  const runTestLeague = async () => {
    setLoading(true);
    try {
      const res = await apiClient.post('/admin/create-test-league');
      showToast(res.data.message || 'League Generated!', 'success');
    } catch (_err) {
      showToast('Failed to create Test League', 'error');
    } finally {
      setLoading(false);
    }
  };

  const resetDraft = async () => {
    if (!window.confirm('⚠️ DANGER: This will wipe all draft picks. Continue?'))
      return;
    setLoading(true);
    try {
      await apiClient.post('/admin/reset-draft');
      setLastSync('Draft Reset: ' + new Date().toLocaleTimeString());
      showToast('Draft history purged!', 'success');
    } catch (err) {
      showToast('Reset failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const runUatDraftReset = async () => {
    if (!window.confirm('⚠️ This will clear draft picks, waivers, trades, and matchups for The Big Show. Continue?'))
      return;

    setLoading(true);
    try {
      const res = await apiClient.post('/admin/tools/uat-draft-reset');
      showToast(res.data.detail || 'UAT Draft Reset complete', 'success');
      setLastSync('UAT Draft Reset: ' + new Date().toLocaleTimeString());
    } catch (err) {
      const errorMsg =
        err.response?.data?.detail ||
        err.response?.statusText ||
        err.message ||
        'UAT Draft Reset failed';
      showToast(errorMsg, 'error');
    } finally {
      setLoading(false);
    }
  };

  const runUatTeamReset = async () => {
    if (!window.confirm('⚠️ This will sync NFL data and auto-seed full rosters (starter + bench) for UAT. Continue?'))
      return;

    setLoading(true);
    try {
      const res = await apiClient.post('/admin/tools/uat-team-reset', {}, { timeout: 300000 });
      showToast(res.data.detail || 'UAT Team Reset complete', 'success');
      setLastSync('UAT Team Reset: ' + new Date().toLocaleTimeString());
    } catch (err) {
      const errorMsg =
        err.response?.data?.detail ||
        err.response?.statusText ||
        err.message ||
        'UAT Team Reset failed';
      showToast(errorMsg, 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto text-white min-h-screen">
      <div className="flex items-center gap-4 mb-10 border-b border-slate-700 pb-6">
        <FiTool className="text-4xl text-purple-500" />
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Site Admin
          </h1>
          <p className="text-slate-400 text-sm">
            System-level and maintenance tools
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
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
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl hover:border-purple-500/30 transition">
          <div className="flex justify-between items-start mb-4">
            <FiTrash2 className="text-purple-400 text-3xl" />
            <div className="bg-purple-900/30 text-purple-400 text-xs font-bold px-2 py-1 rounded">
              UAT
            </div>
          </div>
          <h3 className="text-xl font-bold mb-2">UAT Draft Reset</h3>
          <p className="text-slate-400 text-sm mb-6 min-h-[40px]">
            Reset draft artifacts for The Big Show so UAT draft validation can run from a clean state.
          </p>
          <button
            onClick={runUatDraftReset}
            disabled={loading}
            className={`w-full py-3 rounded-xl font-black uppercase flex items-center justify-center gap-2 transition ${loading ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-purple-600 hover:bg-purple-500 text-white'}`}
          >
            <FiTrash2 />
            {loading ? 'Resetting...' : 'Run UAT Draft Reset'}
          </button>
        </div>
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl hover:border-green-500/30 transition">
          <div className="flex justify-between items-start mb-4">
            <FiUsers className="text-green-400 text-3xl" />
            <div className="bg-green-900/30 text-green-400 text-xs font-bold px-2 py-1 rounded">
              UAT
            </div>
          </div>
          <h3 className="text-xl font-bold mb-2">UAT Team Reset</h3>
          <p className="text-slate-400 text-sm mb-6 min-h-[40px]">
            Populate teams with starter and bench rosters for in-season UAT (waivers, trades, commissioner actions).
          </p>
          <button
            onClick={runUatTeamReset}
            disabled={loading}
            className={`w-full py-3 rounded-xl font-black uppercase flex items-center justify-center gap-2 transition ${loading ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-green-600 hover:bg-green-500 text-white'}`}
          >
            <FiUsers />
            {loading ? 'Seeding...' : 'Run UAT Team Reset'}
          </button>
        </div>
      </div>
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
