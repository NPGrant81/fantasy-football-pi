import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FiSettings,
  FiUsers,
  FiShield,
  FiActivity,
  FiDollarSign,
  FiTool,
  FiRepeat,
  FiBookOpen,
  FiGrid,
} from 'react-icons/fi';

// Professional Imports
import apiClient from '@api/client';
import DraftBudgetsModal from './components/DraftBudgetsModal';
import AdminActionCard from '@components/admin/AdminActionCard';
import {
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '@utils/uiStandards';

// --- 1.1 STATIC DATA (Declared Outside to avoid re-creations) ---
export default function CommissionerDashboard() {
  // --- 1.2 STATE MANAGEMENT ---
  const [, setSettings] = useState(null);
  const [, setAllUsers] = useState([]);
  const [loading, setLoading] = useState(true); // 1.2.1 Start true to prevent cascading renders
  const [showBudgets, setShowBudgets] = useState(false);
  const navigate = useNavigate();

  const leagueId = localStorage.getItem('fantasyLeagueId');

  // --- 1.3 DATA RETRIEVAL (The Engine) ---
  const loadData = useCallback(async () => {
    if (!leagueId) {
      setLoading(false);
      return;
    }

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
      <div
        className={`${pageShell} text-center mt-20 animate-pulse text-slate-600 dark:text-slate-400 font-black`}
      >
        Entering The War Room...
      </div>
    );
  }

  return (
    <div className={`${pageShell} min-h-screen text-slate-900 dark:text-white`}>
      <div className={`${pageHeader} flex items-start gap-3`}>
        <FiTool className="mt-1 text-2xl text-yellow-500" />
        <div>
          <h1 className={pageTitle}>Commissioner Control Panel</h1>
          <p className={pageSubtitle}>
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
          tone="yellow"
        />
        <AdminActionCard
          icon={FiSettings}
          badge="RULES"
          title="Edit Lineup Rules"
          description="Control roster size, position limits, and lineup submission behavior."
          onClick={() => navigate('/commissioner/lineup-rules')}
          loading={false}
          actionLabel="Edit Lineup Rules"
          tone="purple"
        />
        <AdminActionCard
          icon={FiUsers}
          badge="OWNERS"
          title="Invite/Manage Team Owners"
          description="Invite new owners, manage teams, and verify league access."
          onClick={() => navigate('/commissioner/manage-owners')}
          loading={false}
          actionLabel="Manage Owners"
          tone="blue"
        />
        <AdminActionCard
          icon={FiActivity}
          badge="WAIVERS"
          title="Set Waiver Wire Rules"
          description="Set rules for waiver claims, priorities, and deadlines."
          onClick={() => navigate('/commissioner/manage-waiver-rules')}
          loading={false}
          actionLabel="Edit Waiver Rules"
          tone="green"
        />
        <AdminActionCard
          icon={FiShield}
          badge="TRADES"
          title="Set Trade Rules"
          description="Configure trade review, veto, and deadlines."
          onClick={() => navigate('/commissioner/manage-trades')}
          loading={false}
          actionLabel="Edit Trade Rules"
          tone="yellow"
        />
        <AdminActionCard
          icon={FiSettings}
          badge="SCORING"
          title="Manage Scoring Rules"
          description="Create and revise scoring events, run preview simulations, and trigger approved recalculations."
          onClick={() => navigate('/commissioner/manage-scoring-rules')}
          loading={false}
          actionLabel="Edit Scoring Rules"
          tone="red"
        />
        <AdminActionCard
          icon={FiGrid}
          badge="DIVISIONS"
          title="Manage Divisions"
          description="Configure division count, names, assignment method, and finalize seasonal groupings."
          onClick={() => navigate('/commissioner/manage-divisions')}
          loading={false}
          actionLabel="Edit Divisions"
          tone="purple"
        />
        <AdminActionCard
          icon={FiRepeat}
          badge="KEEPERS"
          title="Keeper Rules"
          description="Configure keeper limits, values, and veto/reset."
          onClick={() => navigate('/commissioner/keeper-rules')}
          loading={false}
          actionLabel="Open Keeper Settings"
          tone="indigo"
        />
        <AdminActionCard
          icon={FiBookOpen}
          badge="LEDGER"
          title="Ledger Statement"
          description="Review owner transaction history and derived balances."
          onClick={() => navigate('/commissioner/ledger-statement')}
          loading={false}
          actionLabel="View Ledger"
          tone="blue"
        />
      </div>
    </div>
  );
}
