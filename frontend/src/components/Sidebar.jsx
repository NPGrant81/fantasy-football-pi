import { Link } from 'react-router-dom'
import { FiX, FiGrid, FiUsers, FiActivity, FiTrendingUp, FiSettings } from 'react-icons/fi'

export default function Sidebar({ isOpen, onClose, username, leagueId }) {
  
  // The "Rectangle Block" Component (Mini Version for Sidebar)
  const MenuBlock = ({ to, title, desc, icon: Icon, colorClass }) => (
    <Link 
      to={to} 
      onClick={onClose}
      className={`group relative overflow-hidden block w-full text-left p-4 mb-3 rounded-xl border border-slate-700 hover:border-white transition-all shadow-lg ${colorClass}`}
    >
      <div className="flex items-center gap-4 relative z-10">
        <div className="p-3 bg-black/20 rounded-lg text-white">
          <Icon size={24} />
        </div>
        <div>
          <h3 className="font-black text-lg text-white leading-none uppercase italic tracking-tighter">{title}</h3>
          <p className="text-xs text-white/80 mt-1 font-medium">{desc}</p>
        </div>
      </div>
      {/* Background Icon Watermark */}
      <Icon size={80} className="absolute -bottom-4 -right-4 opacity-10 rotate-12 text-white" />
    </Link>
  )

  return (
    <>
      {/* 1. BACKDROP */}
      <div 
        className={`fixed inset-0 bg-black/80 backdrop-blur-sm z-40 transition-opacity duration-300 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      {/* 2. DRAWER */}
      <div className={`fixed top-0 left-0 h-full w-[85%] max-w-sm bg-slate-900 border-r border-slate-700 z-50 transform transition-transform duration-300 shadow-2xl flex flex-col ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        
        {/* Header */}
        <div className="p-6 flex justify-between items-center border-b border-slate-800 bg-slate-950">
           <div>
             <h2 className="text-2xl font-black text-white tracking-tighter">FANTASY<span className="text-yellow-500">Pi</span></h2>
             <p className="text-xs text-slate-500">League ID: {leagueId}</p>
           </div>
           <button onClick={onClose} className="p-2 text-slate-400 hover:text-white bg-slate-800 rounded-full">
             <FiX size={24} />
           </button>
        </div>

        {/* --- THE LAUNCHPAD (Scrollable) --- */}
        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          <div className="text-xs font-bold text-slate-500 uppercase mb-3 ml-1">Game Modes</div>
          
          {/* 1. WAR ROOM */}
          <MenuBlock 
            to="/draft"
            title="War Room"
            desc="Live Auction Draft"
            icon={FiGrid}
            colorClass="bg-gradient-to-r from-yellow-600 to-yellow-500"
          />

          {/* 2. MY TEAM */}
          <MenuBlock 
            to="/team"
            title="My Team"
            desc="Roster & Lineups"
            icon={FiUsers}
            colorClass="bg-gradient-to-r from-green-700 to-green-600"
          />

          {/* 3. MATCHUPS */}
          <MenuBlock 
            to="/matchups"
            title="Matchups"
            desc="Live Scoring"
            icon={FiActivity}
            colorClass="bg-gradient-to-r from-red-700 to-red-600"
          />

          {/* 4. WAIVERS */}
          <MenuBlock 
            to="/waivers"
            title="Waiver Wire"
            desc="Bids & Free Agents"
            icon={FiTrendingUp}
            colorClass="bg-gradient-to-r from-blue-700 to-blue-600"
          />

           <div className="my-6 border-t border-slate-800"></div>
           
           <div className="text-xs font-bold text-slate-500 uppercase mb-3 ml-1">Settings</div>
           
           <Link to="/admin" onClick={onClose} className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition">
             <FiSettings /> <span>League Settings</span>
           </Link>
        </nav>

        {/* Footer */}
        <div className="p-6 bg-slate-950 border-t border-slate-800">
          <div className="flex items-center gap-3">
             <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-600 flex items-center justify-center font-bold text-white">
               {username ? username[0].toUpperCase() : '?'}
             </div>
             <div>
               <p className="text-sm font-bold text-white">{username}</p>
               <button className="text-xs text-red-400 hover:text-red-300">Log Out</button>
             </div>
          </div>
        </div>

      </div>
    </>
  )
}