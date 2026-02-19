import { useEffect, useState, useCallback } from 'react';
import {
  FiSettings,
  FiUsers,
  FiShield,
  FiChevronLeft,
  FiSave,
  FiPlus,
  FiTrash2,
  FiUserPlus,
  FiUserX,
  FiActivity,
  FiUserCheck,
  FiDollarSign,
} from 'react-icons/fi';

// Professional Imports
import apiClient from '@api/client';
import DraftBudgetsModal from './components/DraftBudgetsModal';

// --- 1.1 STATIC DATA (Declared Outside to avoid re-creations) ---
const SCORING_MENU = {
  Passing: [
    'Passing TD (6 pts)',
    'Bonus: Pass TD Length (40-49 yds)',
    'Passing Yards (0.1 pt per yard)',
  ],
  Rushing: ['Rushing TD (10 pts)', 'Rushing Yards (0.3 pt per yard)'],
  // ... (keep your full list here)
};

export default function CommissionerDashboard() {
  // --- 1.2 STATE MANAGEMENT ---
  const [view, setView] = useState('menu');
  const [settings, setSettings] = useState(null);
  const [allUsers, setAllUsers] = useState([]);
  const [loading, setLoading] = useState(true); // 1.2.1 Start true to prevent cascading renders
  const [unsavedChanges, setUnsavedChanges] = useState(false);
  const [activeTab, setActiveTab] = useState('Passing');
  const [newOwnerName, setNewOwnerName] = useState('');
  const [newOwnerEmail, setNewOwnerEmail] = useState('');
  const [showBudgets, setShowBudgets] = useState(false);

  const leagueId = localStorage.getItem('fantasyLeagueId');

  // --- 1.3 DATA RETRIEVAL (The Engine) ---
  const loadData = useCallback(async () => {
    if (!leagueId) return;

    try {
      // Using @api/client handles the Base URL and Token automatically
      const [setRes, userRes] = await Promise.all([
        apiClient.get(`/leagues/${leagueId}/settings`),
        apiClient.get(`/leagues/owners?league_id=${leagueId}`),
      ]);

      setSettings(setRes.data);
      setAllUsers(userRes.data);
    } catch (err) {
      console.error('Commissioner load failed:', err);
    } finally {
      setLoading(false);
    }
  }, [leagueId]);

  // 1.3.1 Trigger load on mount
  useEffect(() => {
    loadData();
  }, [loadData]);

  // --- 1.4 EVENT HANDLERS ---
  const handleUpdate = (field, value) => {
    setSettings({ ...settings, [field]: value });
    setUnsavedChanges(true);
  };

  const handleRuleChange = (idx, field, val) => {
    const n = [...settings.scoring_rules];
    n[idx][field] = val;
    setSettings({ ...settings, scoring_rules: n });
    setUnsavedChanges(true);
  };

  const saveSettings = async () => {
    try {
      await apiClient.put(`/leagues/${leagueId}/settings`, settings);
      alert('Settings Secured.');
      setUnsavedChanges(false);
    } catch (err) {
      alert('Error saving settings.');
    }
  };

  const handleCreateOwner = async () => {
    if (!newOwnerName) return;
    try {
      await apiClient.post(`/leagues/owners`, {
        username: newOwnerName,
        email: newOwnerEmail,
      });
      alert(`User ${newOwnerName} drafted to the platform.`);
      setNewOwnerName('');
      setNewOwnerEmail('');
      loadData();
    } catch (err) {
      alert('Creation failed: ' + (err.response?.data?.detail || err.message));
    }
  };

  // --- 2.1 RENDER LOGIC ---

  if (loading) {
    return (
      <div className="text-white text-center mt-20 animate-pulse font-black uppercase tracking-widest">
        Entering The War Room...
      </div>
    );
  }

  return (
    <div className="p-8 max-w-3xl mx-auto text-white">
      <h1 className="text-4xl font-black italic uppercase tracking-tighter mb-8">
        Commissioner Control Panel
      </h1>
      <DraftBudgetsModal
        open={showBudgets}
        onClose={() => setShowBudgets(false)}
        leagueId={leagueId}
      />
      {/* Commissioner Modals */}
      <div className="space-y-6">
        <div className="bg-slate-900 border border-yellow-700 rounded-xl p-6">
          <h2 className="text-2xl font-bold text-yellow-400 mb-2 flex items-center gap-2">
            <FiDollarSign /> Set Draft Budgets
          </h2>
          <p className="text-slate-400 mb-2">
            Assign draft budgets for each owner and season.
          </p>
          <button
            className="bg-yellow-500 hover:bg-yellow-400 text-black px-4 py-2 rounded font-bold"
            onClick={() => setShowBudgets(true)}
          >
            Edit Draft Budgets
          </button>
        </div>
        {/* Scoring Rules Modal Stub */}
        <div className="bg-slate-900 border border-purple-700 rounded-xl p-6">
          <h2 className="text-2xl font-bold text-purple-400 mb-2 flex items-center gap-2">
            <FiSettings /> Set Scoring Rules
          </h2>
          <p className="text-slate-400 mb-2">
            Configure how points are awarded for all league actions.
          </p>
          {/* TODO: Implement scoring rules modal */}
          <button className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded font-bold">
            Edit Scoring Rules
          </button>
        </div>
        {/* Owner Management Modal Stub */}
        <div className="bg-slate-900 border border-blue-700 rounded-xl p-6">
          <h2 className="text-2xl font-bold text-blue-400 mb-2 flex items-center gap-2">
            <FiUsers /> Invite/Manage Team Owners
          </h2>
          <p className="text-slate-400 mb-2">
            Invite new owners, manage teams, and verify league access.
          </p>
          {/* TODO: Implement owner management modal */}
          <button className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded font-bold">
            Manage Owners
          </button>
        </div>
        {/* Waiver Wire Rules Modal Stub */}
        <div className="bg-slate-900 border border-green-700 rounded-xl p-6">
          <h2 className="text-2xl font-bold text-green-400 mb-2 flex items-center gap-2">
            <FiActivity /> Set Waiver Wire Rules
          </h2>
          <p className="text-slate-400 mb-2">
            Set rules for waiver claims, priorities, and deadlines.
          </p>
          {/* TODO: Implement waiver wire rules modal */}
          <button className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded font-bold">
            Edit Waiver Rules
          </button>
        </div>
        {/* Trade Rules Modal Stub */}
        <div className="bg-slate-900 border border-yellow-700 rounded-xl p-6">
          <h2 className="text-2xl font-bold text-yellow-400 mb-2 flex items-center gap-2">
            <FiShield /> Set Trade Rules
          </h2>
          <p className="text-slate-400 mb-2">
            Configure trade review, veto, and deadlines.
          </p>
          {/* TODO: Implement trade rules modal */}
          <button className="bg-yellow-500 hover:bg-yellow-400 text-black px-4 py-2 rounded font-bold">
            Edit Trade Rules
          </button>
        </div>
      </div>
    </div>
  );
}
