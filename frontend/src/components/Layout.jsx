// frontend/src/components/Layout.jsx
import { useState } from 'react';
import { FiMenu } from 'react-icons/fi';
import { layoutAlertBar } from '../utils/uiStandards';
import Sidebar from './Sidebar';
import ThemeToggle from './ThemeToggle';

export default function Layout({ children, username, leagueId, alert }) {
  // --- 1.1 UI STATE ---
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const hasAlert = Boolean(alert && String(alert).trim());

  // --- 2.1 RENDER LOGIC (The Shell) ---
  return (
    <div className="min-h-screen w-full bg-white dark:bg-slate-950 text-black dark:text-white font-sans overflow-hidden">
      {/* 2.2 TOP NAVIGATION BAR */}
      <header className="sticky top-0 z-30 bg-slate-100/80 dark:bg-slate-900/80 backdrop-blur border-b border-slate-300 dark:border-slate-800 h-16 px-4 flex items-center justify-between text-black dark:text-white">
        {/* Mobile Trigger */}
        <button
          onClick={() => setIsSidebarOpen(true)}
          className="p-2 text-yellow-500 hover:bg-slate-800 rounded transition"
        >
          <FiMenu size={28} />
        </button>

        {/* Branding */}
        <div className="flex items-center gap-2 font-black text-xl tracking-tighter italic uppercase">
          <img
            src={import.meta.env.BASE_URL + 'src/assets/react.svg'}
            alt="FantasyFootball-PI Logo"
            className="w-8 h-8"
          />
          FANTASY<span className="text-slate-600">Pi</span>
        </div>
        {/* theme toggle */}
        <ThemeToggle />
      </header>

      {/* 2.3 SUB‑HEADER / ALERT BAR */}
      {hasAlert && <div className={layoutAlertBar}>{alert}</div>}

      {/* 2.4 NAVIGATION DRAWER */}
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        username={username}
        leagueId={leagueId}
      />

      {/* 2.4 PAGE VIEWPORT */}
      <main className="flex-1 w-full p-4 md:p-6 animate-fade-in">
        {/* This is where your Route elements (Dashboard, DraftBoard, etc.) render */}
        {children}
      </main>
    </div>
  );
}
