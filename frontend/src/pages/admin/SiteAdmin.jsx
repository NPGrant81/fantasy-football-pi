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
import AdminActionCard from '@components/admin/AdminActionCard';

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
    } catch (err) {
      showToast(
        err.response?.data?.detail || err.message || 'Failed to create Test League',
        'error'
      );
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
      showToast(err.response?.data?.detail || err.message || 'Reset failed', 'error');
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
          {lastSync && (
            <p className="text-xs text-slate-500 mt-1">Last action: {lastSync}</p>
          )}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <AdminActionCard
          icon={FiRefreshCw}
          badge="DATA"
          title="NFL Reality Sync"
          description="Force a refresh of all player teams, injury statuses, and bye weeks."
          onClick={runSync}
          disabled={loading}
          loading={loading}
          loadingLabel="Syncing..."
          actionLabel="Run Sync"
          iconSpinsOnLoading
          accent={{
            hoverBorder: 'hover:border-blue-500/30',
            icon: 'text-blue-400',
            badge: 'bg-blue-900/30 text-blue-400',
            button: 'bg-blue-600 hover:bg-blue-500 text-white',
          }}
        />
        <AdminActionCard
          icon={FiBox}
          badge="SANDBOX"
          title="Test League Gen"
          description='Create "Test League 2026" with 12 dummy owners for testing.'
          onClick={runTestLeague}
          disabled={loading}
          loading={loading}
          loadingLabel="Working..."
          actionLabel="Generate League"
          accent={{
            hoverBorder: 'hover:border-yellow-500/30',
            icon: 'text-yellow-400',
            badge: 'bg-yellow-900/30 text-yellow-400',
            button: 'bg-yellow-600 hover:bg-yellow-500 text-white',
          }}
        />
        <AdminActionCard
          icon={FiTrash2}
          badge="DANGER"
          title="Reset Draft"
          description="Wipe all current draft picks and reset the board for a fresh start."
          onClick={resetDraft}
          disabled={loading}
          loading={loading}
          loadingLabel="Resetting..."
          actionLabel="Reset Board"
          accent={{
            hoverBorder: 'hover:border-red-500/30',
            icon: 'text-red-400',
            badge: 'bg-red-900/30 text-red-400',
            button: 'bg-red-600 hover:bg-red-500 text-white',
          }}
        />
        <AdminActionCard
          icon={FiTrash2}
          badge="UAT"
          title="UAT Draft Reset"
          description="Reset draft artifacts for The Big Show so UAT draft validation can run from a clean state."
          onClick={runUatDraftReset}
          disabled={loading}
          loading={loading}
          loadingLabel="Resetting..."
          actionLabel="Run UAT Draft Reset"
          accent={{
            hoverBorder: 'hover:border-purple-500/30',
            icon: 'text-purple-400',
            badge: 'bg-purple-900/30 text-purple-400',
            button: 'bg-purple-600 hover:bg-purple-500 text-white',
          }}
        />
        <AdminActionCard
          icon={FiUsers}
          badge="UAT"
          title="UAT Team Reset"
          description="Populate teams with starter and bench rosters for in-season UAT (waivers, trades, commissioner actions)."
          onClick={runUatTeamReset}
          disabled={loading}
          loading={loading}
          loadingLabel="Seeding..."
          actionLabel="Run UAT Team Reset"
          accent={{
            hoverBorder: 'hover:border-green-500/30',
            icon: 'text-green-400',
            badge: 'bg-green-900/30 text-green-400',
            button: 'bg-green-600 hover:bg-green-500 text-white',
          }}
        />
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
