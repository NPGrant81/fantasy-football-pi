import { NavLink } from 'react-router-dom';
import { useEffect, useState } from 'react';
import apiClient from '@api/client';
import { layerBackdrop, layerDrawer } from '@utils/uiStandards';
import BrandMark from './BrandMark';

import {
  FiX,
  FiGrid,
  FiUsers,
  FiActivity,
  FiBarChart2,
  FiTrendingUp,
  FiSettings,
  FiShield,
  FiHome,
  FiAward,
  FiRepeat,
  FiAlertTriangle,
  FiClock,
  FiRefreshCw,
  FiArrowLeftRight,
} from 'react-icons/fi';

// 1.1 COMPONENT DECLARED OUTSIDE (Fixes "Cannot create components during render")
const MenuBlock = ({ to, title, desc, icon, onClick, end = true }) => {
  const Icon = icon;

  return (
    <NavLink
      to={to}
      onClick={onClick}
      end={end}
      className={({ isActive }) =>
        `group relative mb-2 block w-full overflow-hidden rounded-xl border p-3 text-left shadow-sm transition-all ${
          isActive
            ? 'border-cyan-500 bg-cyan-50 dark:border-cyan-600 dark:bg-slate-800'
            : 'border-slate-300 bg-white hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800'
        }`
      }
    >
      <div className="flex items-center gap-4 relative z-10">
        <div className="rounded-lg bg-slate-200 p-3 text-slate-700 dark:bg-slate-800 dark:text-slate-100">
          <Icon size={24} />
        </div>
        <div>
          <h3 className="leading-none font-black text-lg uppercase italic tracking-tighter text-slate-900 dark:text-white">
            {title}
          </h3>
          <p className="mt-1 text-xs font-medium text-slate-600 dark:text-slate-400">
            {desc}
          </p>
        </div>
      </div>
      <Icon
        size={80}
        className="absolute -bottom-4 -right-4 rotate-12 text-slate-400 opacity-20 dark:text-slate-500"
      />
    </NavLink>
  );
};

export default function Sidebar({ isOpen, onClose, username, leagueId, onLogout, isCommissioner, isSuperuser, onLeagueSwitch }) {
  const [leagueName, setLeagueName] = useState('');

  useEffect(() => {
    if (leagueId) {
      apiClient
        .get(`/leagues/${leagueId}`)
        .then((res) => setLeagueName(res.data.name))
        .catch(() => setLeagueName('League'));
    }
  }, [leagueId]);
  return (
    <>
      <div
        className={`fixed inset-0 bg-black/80 backdrop-blur-sm ${layerBackdrop} transition-opacity duration-300 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      <div
        className={`fixed top-0 left-0 ${layerDrawer} flex h-full w-[85%] transform flex-col border-r border-slate-300 bg-white shadow-2xl transition-transform duration-300 dark:border-slate-800 dark:bg-slate-950 sm:max-w-sm md:max-w-md ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-300 bg-slate-100 p-6 dark:border-slate-800 dark:bg-slate-900">
          <BrandMark
            containerClassName="flex items-center gap-2"
            imageClassName="w-7 h-7"
            textClassName="text-2xl font-black tracking-tighter text-slate-900 dark:text-white"
          />
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {leagueName ? leagueName : 'League'}
          </p>
          <button
            onClick={onClose}
            className="rounded-full bg-slate-200 p-2 text-slate-600 hover:bg-slate-300 hover:text-slate-900 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-white"
          >
            <FiX size={24} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          <div className="mb-2">
            <MenuBlock
              to="/"
              title="Home"
              desc="League Dashboard"
              icon={FiHome}
              onClick={onClose}
            />
          </div>
          <div className="mb-3 ml-1 text-xs font-bold uppercase text-slate-500 dark:text-slate-400">
            Game Modes
          </div>

          <MenuBlock
            to="/draft"
            title="War Room"
            desc="Live Auction Draft"
            icon={FiGrid}
            onClick={onClose}
          />

          <MenuBlock
            to="/draft-day-analyzer"
            title="Draft Day Analyzer"
            desc="Strategy, Advisor, Sim"
            icon={FiBarChart2}
            onClick={onClose}
          />

          <MenuBlock
            to="/team"
            title="My Team"
            desc="Roster & Lineups"
            icon={FiUsers}
            onClick={onClose}
          />

          <MenuBlock
            to="/matchups"
            title="Matchups"
            desc="Live Scoring"
            icon={FiActivity}
            onClick={onClose}
          />

          <MenuBlock
            to="/waivers"
            title="Waiver Wire"
            desc="Bids & Free Agents"
            icon={FiTrendingUp}
            onClick={onClose}
          />

          <MenuBlock
            to="/keepers"
            title="Keepers"
            desc="Manage off‑season keepers"
            icon={FiRepeat}
            onClick={onClose}
          />

          <MenuBlock
            to="/trades/submit"
            title="Trades"
            desc="Propose a trade"
            icon={FiArrowLeftRight}
            onClick={onClose}
          />

          <MenuBlock
            to="/analytics"
            title="Analytics"
            desc="League Charts"
            icon={FiBarChart2}
            onClick={onClose}
          />

          <MenuBlock
            to="/league-history"
            title="League History"
            desc="Legacy Analytics & Records"
            icon={FiClock}
            onClick={onClose}
            end={false}
          />

          <MenuBlock
            to="/ledger"
            title="Ledger"
            desc="My bank statement"
            icon={FiTrendingUp}
            onClick={onClose}
          />

          <MenuBlock
            to="/playoffs"
            title="Playoff Bracket"
            desc="View bracket"
            icon={FiAward}
            onClick={onClose}
          />

          <div className="my-6 border-t border-slate-300 dark:border-slate-800"></div>
          <div className="mb-3 ml-1 text-xs font-bold uppercase text-slate-500 dark:text-slate-400">
            Settings
          </div>

          {isCommissioner && (
            <NavLink
              to="/commissioner"
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg p-3 transition ${
                  isActive
                    ? 'bg-cyan-50 text-cyan-700 dark:bg-slate-800 dark:text-cyan-400'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white'
                }`
              }
            >
              <FiShield className="text-cyan-500" /> <span>Commissioner</span>
            </NavLink>
          )}

          <NavLink
            to="/bug-report"
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg p-3 transition ${
                isActive
                  ? 'bg-cyan-50 text-cyan-700 dark:bg-slate-800 dark:text-cyan-400'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white'
              }`
            }
          >
            <FiAlertTriangle className="text-cyan-500" />{' '}
            <span>Report a Bug</span>
          </NavLink>

          <NavLink
            to="/admin"
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg p-3 transition ${
                isActive
                  ? 'bg-cyan-50 text-cyan-700 dark:bg-slate-800 dark:text-cyan-400'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white'
              }`
            }
          >
            <FiSettings /> <span>Admin Settings</span>
          </NavLink>
        </nav>

        <div className="border-t border-slate-300 bg-slate-100 p-6 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-400 bg-slate-200 font-bold text-slate-800 dark:border-slate-600 dark:bg-slate-800 dark:text-white">
              {username ? username[0].toUpperCase() : '?'}
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900 dark:text-white">
                {username}
              </p>
              <div className="flex items-center gap-3 mt-0.5">
                <button
                  onClick={() => {
                    if (typeof onLogout === 'function') onLogout();
                    if (typeof onClose === 'function') onClose();
                  }}
                  className="text-xs text-red-500 hover:text-red-400 dark:text-red-400 dark:hover:text-red-300"
                >
                  Log Out
                </button>
                {isSuperuser && (
                  <button
                    onClick={() => {
                      if (typeof onLeagueSwitch === 'function') onLeagueSwitch();
                      if (typeof onClose === 'function') onClose();
                    }}
                    className="flex items-center gap-1 text-xs text-yellow-500 hover:text-yellow-400"
                  >
                    <FiRefreshCw size={10} /> Switch League
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
