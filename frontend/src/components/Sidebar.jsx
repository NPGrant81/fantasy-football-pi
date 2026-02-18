import { Link } from 'react-router-dom';

import {
  FiX,
  FiGrid,
  FiUsers,
  FiActivity,
  FiTrendingUp,
  FiSettings,
  FiShield,
} from 'react-icons/fi';
import { menuGradients, bgColors, textColors, borderColors } from '../utils/uiHelpers';

// 1.1 COMPONENT DECLARED OUTSIDE (Fixes "Cannot create components during render")
const MenuBlock = ({ to, title, desc, icon: Icon, gradient, onClick }) => (
  <Link
    to={to}
    onClick={onClick}
    className={`group relative overflow-hidden block w-full text-left p-4 mb-3 rounded-xl border ${borderColors.main} hover:border-white transition-all shadow-lg ${gradient}`}
  >
    <div className="flex items-center gap-4 relative z-10">
      <div className="p-3 bg-black/20 rounded-lg text-white">
        <Icon size={24} />
      </div>
      <div>
        <h3 className="font-black text-lg text-white leading-none uppercase italic tracking-tighter">
          {title}
        </h3>
        <p className="text-xs text-white/80 mt-1 font-medium">{desc}</p>
      </div>
    </div>
    <Icon
      size={80}
      className="absolute -bottom-4 -right-4 opacity-10 rotate-12 text-white"
    />
  </Link>
);

export default function Sidebar({ isOpen, onClose, username, leagueId }) {
  return (
    <>
      <div
        className={`fixed inset-0 bg-black/80 backdrop-blur-sm z-40 transition-opacity duration-300 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      <div
        className={`fixed top-0 left-0 h-full w-[85%] max-w-sm bg-slate-900 border-r border-slate-700 z-50 transform transition-transform duration-300 shadow-2xl flex flex-col ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="p-6 flex justify-between items-center border-b border-slate-800 bg-slate-950">
          <div>
            <h2 className="text-2xl font-black text-white tracking-tighter">
              FANTASY<span className="text-yellow-500">Pi</span>
            </h2>
            <p className="text-xs text-slate-500">League ID: {leagueId}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white bg-slate-800 rounded-full"
          >
            <FiX size={24} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          <div className="text-xs font-bold text-slate-500 uppercase mb-3 ml-1">
            Game Modes
          </div>


          <MenuBlock
            to="/draft"
            title="War Room"
            desc="Live Auction Draft"
            icon={FiGrid}
            gradient={menuGradients.draft}
            onClick={onClose}
          />

          <MenuBlock
            to="/team"
            title="My Team"
            desc="Roster & Lineups"
            icon={FiUsers}
            gradient={menuGradients.team}
            onClick={onClose}
          />

          <MenuBlock
            to="/matchups"
            title="Matchups"
            desc="Live Scoring"
            icon={FiActivity}
            gradient={menuGradients.matchups}
            onClick={onClose}
          />

          <MenuBlock
            to="/waivers"
            title="Waiver Wire"
            desc="Bids & Free Agents"
            icon={FiTrendingUp}
            gradient={menuGradients.waivers}
            onClick={onClose}
          />

          <div className="my-6 border-t border-slate-800"></div>
          <div className="text-xs font-bold text-slate-500 uppercase mb-3 ml-1">
            Settings
          </div>

          <Link
            to="/commissionerdashboard"
            onClick={onClose}
            className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
          >
            <FiShield className="text-yellow-400" /> <span>Commissioner</span>
          </Link>

          <Link
            to="/admin"
            onClick={onClose}
            className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
          >
            <FiSettings /> <span>Admin Settings</span>
          </Link>
        </nav>

        <div className="p-6 bg-slate-950 border-t border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-600 flex items-center justify-center font-bold text-white">
              {username ? username[0].toUpperCase() : '?'}
            </div>
            <div>
              <p className="text-sm font-bold text-white">{username}</p>
              <button className="text-xs text-red-400 hover:text-red-300">
                Log Out
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
