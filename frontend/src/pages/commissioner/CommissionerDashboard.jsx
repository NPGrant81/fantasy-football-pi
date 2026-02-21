import { useEffect, useState, useCallback } from 'react';
import {
  FiSettings,
  FiUsers,
  FiShield,
  FiActivity,
  FiDollarSign,
  FiTool,
} from 'react-icons/fi';

// Professional Imports
import apiClient from '@api/client';
import DraftBudgetsModal from './components/DraftBudgetsModal';
import AdminActionCard from '@components/admin/AdminActionCard';

// --- 1.1 STATIC DATA (Declared Outside to avoid re-creations) ---
export default function CommissionerDashboard() {
  // --- 1.2 STATE MANAGEMENT ---
  const [, setSettings] = useState(null);
  const [, setAllUsers] = useState([]);
  const [loading, setLoading] = useState(true); // 1.2.1 Start true to prevent cascading renders
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

  // --- 2.1 RENDER LOGIC ---

  if (loading) {
    return (
      <div className="text-white text-center mt-20 animate-pulse font-black uppercase tracking-widest">
        Entering The War Room...
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto text-white min-h-screen">
      <div className="flex items-center gap-4 mb-10 border-b border-slate-700 pb-6">
        <FiTool className="text-4xl text-yellow-500" />
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Commissioner Control Panel
          </h1>
          <p className="text-slate-400 text-sm">
            League-level controls and configuration tools
          </p>
        </div>
      </div>
      <DraftBudgetsModal
        open={showBudgets}
        onClose={() => setShowBudgets(false)}
        leagueId={leagueId}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <AdminActionCard
          icon={FiDollarSign}
          badge="LEAGUE"
          title="Set Draft Budgets"
          description="Assign draft budgets for each owner and season."
          onClick={() => setShowBudgets(true)}
          loading={false}
          actionLabel="Edit Draft Budgets"
          accent={{
            hoverBorder: 'hover:border-yellow-500/30',
            icon: 'text-yellow-400',
            badge: 'bg-yellow-900/30 text-yellow-400',
            button: 'bg-yellow-500 hover:bg-yellow-400 text-black',
          }}
        />
        <AdminActionCard
          icon={FiSettings}
          badge="RULES"
          title="Set Scoring Rules"
          description="Configure how points are awarded for all league actions."
          loading={false}
          actionLabel="Edit Scoring Rules"
          accent={{
            hoverBorder: 'hover:border-purple-500/30',
            icon: 'text-purple-400',
            badge: 'bg-purple-900/30 text-purple-400',
            button: 'bg-purple-600 hover:bg-purple-500 text-white',
          }}
        />
        <AdminActionCard
          icon={FiUsers}
          badge="OWNERS"
          title="Invite/Manage Team Owners"
          description="Invite new owners, manage teams, and verify league access."
          loading={false}
          actionLabel="Manage Owners"
          accent={{
            hoverBorder: 'hover:border-blue-500/30',
            icon: 'text-blue-400',
            badge: 'bg-blue-900/30 text-blue-400',
            button: 'bg-blue-600 hover:bg-blue-500 text-white',
          }}
        />
        <AdminActionCard
          icon={FiActivity}
          badge="WAIVERS"
          title="Set Waiver Wire Rules"
          description="Set rules for waiver claims, priorities, and deadlines."
          loading={false}
          actionLabel="Edit Waiver Rules"
          accent={{
            hoverBorder: 'hover:border-green-500/30',
            icon: 'text-green-400',
            badge: 'bg-green-900/30 text-green-400',
            button: 'bg-green-600 hover:bg-green-500 text-white',
          }}
        />
        <AdminActionCard
          icon={FiShield}
          badge="TRADES"
          title="Set Trade Rules"
          description="Configure trade review, veto, and deadlines."
          loading={false}
          actionLabel="Edit Trade Rules"
          accent={{
            hoverBorder: 'hover:border-yellow-500/30',
            icon: 'text-yellow-400',
            badge: 'bg-yellow-900/30 text-yellow-400',
            button: 'bg-yellow-500 hover:bg-yellow-400 text-black',
          }}
        />
      </div>
    </div>
  );
}
