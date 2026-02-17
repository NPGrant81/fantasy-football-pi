import { useEffect, useState, useCallback } from 'react';
import { 
    FiSettings, FiUsers, FiShield, FiChevronLeft, FiSave, 
    FiPlus, FiTrash2, FiUserPlus, FiUserX, FiActivity, FiUserCheck 
} from 'react-icons/fi';

// Professional Imports
import apiClient from '@api/client';

// --- 1.1 STATIC DATA (Declared Outside to avoid re-creations) ---
const SCORING_MENU = {
  Passing: ["Passing TD (6 pts)", "Bonus: Pass TD Length (40-49 yds)", "Passing Yards (0.1 pt per yard)"],
  Rushing: ["Rushing TD (10 pts)", "Rushing Yards (0.3 pt per yard)"],
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

  const leagueId = localStorage.getItem('fantasyLeagueId');

  // --- 1.3 DATA RETRIEVAL (The Engine) ---
  const loadData = useCallback(async () => {
    if (!leagueId) return;

    try {
      // Using @api/client handles the Base URL and Token automatically
      const [setRes, userRes] = await Promise.all([
        apiClient.get(`/leagues/${leagueId}/settings`),
        apiClient.get('/owners')
      ]);

      setSettings(setRes.data);
      setAllUsers(userRes.data);
    } catch (err) {
      console.error("Commissioner load failed:", err);
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
      alert("Settings Secured.");
      setUnsavedChanges(false);
    } catch (err) {
      alert("Error saving settings.");
    }
  };

  const handleCreateOwner = async () => {
    if(!newOwnerName) return;
    try {
      await apiClient.post(`/leagues/owners`, { 
        username: newOwnerName, 
        email: newOwnerEmail 
      });
      alert(`User ${newOwnerName} drafted to the platform.`);
      setNewOwnerName('');
      setNewOwnerEmail('');
      loadData(); 
    } catch (err) {
      alert("Creation failed: " + (err.response?.data?.detail || err.message));
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
    <div className="p-8 max-w-7xl mx-auto text-white">
      {/* 2.2 HEADER */}
      <div className="flex justify-between items-center mb-10 border-b border-slate-800 pb-6">
        <div className="flex items-center gap-4">
          {view !== 'menu' && (
            <button onClick={() => setView('menu')} className="p-2 bg-slate-800 rounded-full hover:bg-slate-700 transition">
              <FiChevronLeft size={20} />
            </button>
          )}
          <h1 className="text-4xl font-black italic uppercase tracking-tighter">Commissioner Control</h1>
        </div>
        {unsavedChanges && (
          <button 
            onClick={saveSettings}
            className="flex items-center gap-2 bg-green-600 hover:bg-green-500 text-black px-6 py-2 rounded-lg font-black uppercase transition shadow-[0_0_15px_rgba(22,163,74,0.4)]"
          >
            <FiSave /> Save Changes
          </button>
        )}
      </div>

      {/* 2.3 VIEW LOGIC */}
      {view === 'menu' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <button onClick={() => setView('scoring')} className="p-10 bg-slate-900 border border-slate-800 rounded-[2rem] hover:border-purple-500 transition text-left group">
            <FiSettings className="text-4xl text-purple-500 mb-4 group-hover:scale-110 transition" />
            <h2 className="text-2xl font-bold uppercase tracking-tight">Scoring Rules</h2>
            <p className="text-slate-500 mt-2">Adjust yardage points, TD values, and bonus thresholds.</p>
          </button>
          
          <button onClick={() => setView('users')} className="p-10 bg-slate-900 border border-slate-800 rounded-[2rem] hover:border-blue-500 transition text-left group">
            <FiUsers className="text-4xl text-blue-500 mb-4 group-hover:scale-110 transition" />
            <h2 className="text-2xl font-bold uppercase tracking-tight">Owner Management</h2>
            <p className="text-slate-500 mt-2">Add new owners, manage teams, and verify league access.</p>
          </button>
        </div>
      )}

      {/* Logic for 'scoring' and 'users' views would follow here... */}
    </div>
  );
}