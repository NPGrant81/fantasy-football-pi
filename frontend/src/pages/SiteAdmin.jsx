// frontend/src/pages/SiteAdmin.jsx
import React, { useState } from 'react';
import axios from 'axios';
import { FiRefreshCw, FiTool, FiDatabase, FiCheckCircle } from 'react-icons/fi';
import Toast from '../components/Toast';

export default function SiteAdmin({ token }) {
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const runSync = async () => {
    setLoading(true);
    try {
      await axios.post('http://localhost:8000/admin/tools/sync-nfl', {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setToast({ message: "Sync Started!", type: 'success' });
    } catch (err) {
      setToast({ message: "Sync Failed", type: 'error' });
    }
    setLoading(false);
  };

  return (
    <div className="p-8 max-w-4xl mx-auto text-white">
      <div className="flex items-center gap-4 mb-10 border-b border-slate-700 pb-6">
        <FiTool className="text-4xl text-purple-500" />
        <h1 className="text-4xl font-black uppercase italic tracking-tighter">Mission Control</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* DATA SYNC CARD */}
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
          <FiDatabase className="text-blue-400 text-2xl mb-4" />
          <h3 className="text-xl font-bold mb-2">NFL Reality Sync</h3>
          <p className="text-slate-400 text-sm mb-6">Force a refresh of all player teams, injury statuses, and bye weeks.</p>
          <button 
            onClick={runSync}
            disabled={loading}
            className={`w-full py-3 rounded-xl font-black uppercase flex items-center justify-center gap-2 transition ${loading ? 'bg-slate-700 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500'}`}
          >
            <FiRefreshCw className={loading ? 'animate-spin' : ''} />
            {loading ? 'Syncing...' : 'Run Daily Sync'}
          </button>
        </div>

        {/* SYSTEM STATUS CARD */}
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
          <FiCheckCircle className="text-green-400 text-2xl mb-4" />
          <h3 className="text-xl font-bold mb-2">Platform Health</h3>
          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">CI/CD Status</span>
              <span className="text-green-400 font-mono italic">ONLINE (Green Check)</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">Database Connection</span>
              <span className="text-green-400 font-mono italic">STABLE</span>
            </div>
          </div>
        </div>
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
}
