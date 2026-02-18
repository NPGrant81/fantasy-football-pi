// frontend/src/components/Layout.jsx
import { useState } from 'react';
import { FiMenu } from 'react-icons/fi';
import Sidebar from './Sidebar';

export default function Layout({ children, username, leagueId }) {
  // --- 1.1 UI STATE ---
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // --- 2.1 RENDER LOGIC (The Shell) ---
  return (
    <div className="min-h-screen bg-slate-950 text-white font-sans">
      {/* 2.2 TOP NAVIGATION BAR */}
      <header className="sticky top-0 z-30 bg-slate-900/80 backdrop-blur border-b border-slate-800 h-16 px-4 flex items-center justify-between">
        {/* Mobile Trigger */}
        <button
          onClick={() => setIsSidebarOpen(true)}
          className="p-2 text-yellow-500 hover:bg-slate-800 rounded transition"
        >
          <FiMenu size={28} />
        </button>

        {/* Branding */}
        <div className="flex items-center gap-2 font-black text-xl tracking-tighter italic uppercase">
          <img src={require('../assets/react.svg')} alt="FantasyFootball-PI Logo" className="w-8 h-8" />
          FANTASY<span className="text-slate-600">Pi</span>
        </div>
      </header>

      {/* 2.3 NAVIGATION DRAWER */}
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        username={username}
        leagueId={leagueId}
      />

      {/* 2.4 PAGE VIEWPORT */}
      <main className="p-4 md:p-6 max-w-7xl mx-auto animate-fade-in">
        {/* This is where your Route elements (Dashboard, DraftBoard, etc.) render */}
        {children}
      </main>
    </div>
  );
}
