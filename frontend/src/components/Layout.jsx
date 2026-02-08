import { useState } from 'react'
import { FiMenu } from 'react-icons/fi'
import Sidebar from './Sidebar'

export default function Layout({ children, username, leagueId }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen bg-slate-950 text-white font-sans">
      
      {/* --- TOP BAR (Always Visible) --- */}
      <header className="sticky top-0 z-30 bg-slate-900/80 backdrop-blur border-b border-slate-800 h-16 px-4 flex items-center justify-between">
        
        {/* Hamburger Button */}
        <button 
          onClick={() => setIsSidebarOpen(true)}
          className="p-2 text-yellow-500 hover:bg-slate-800 rounded transition"
        >
          <FiMenu size={28} />
        </button>

        {/* Logo / Title (Centered or Right) */}
        <div className="font-black text-xl tracking-tighter">
          FANTASY<span className="text-slate-600">Pi</span>
        </div>
      </header>

      {/* --- SIDEBAR COMPONENT --- */}
      <Sidebar 
        isOpen={isSidebarOpen} 
        onClose={() => setIsSidebarOpen(false)} 
        username={username}
        leagueId={leagueId}
      />

      {/* --- PAGE CONTENT (Where Home/DraftBoard goes) --- */}
      <main className="p-4 md:p-6 max-w-7xl mx-auto animate-fade-in">
        {children}
      </main>

    </div>
  )
}