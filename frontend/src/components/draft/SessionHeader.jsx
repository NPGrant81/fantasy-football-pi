// frontend/src/components/SessionHeader.jsx
import React from 'react';
import { FiClock, FiUsers, FiAlertTriangle } from 'react-icons/fi';

export default function SessionHeader({ sessionId, rosterSize, onFinalize }) {
  return (
    <div className="flex justify-between items-center py-2 bg-black/40 text-[10px] text-slate-400 mb-4 rounded px-3 border border-slate-800 uppercase tracking-widest">
      <div className="flex gap-6 items-center">
        <div className="flex items-center gap-2">
          <FiClock className="text-purple-500" />
          <span>Session: <span className="text-slate-200 font-mono">{sessionId}</span></span>
        </div>
        <div className="flex items-center gap-2">
          <FiUsers className="text-blue-500" />
          <span>Max Roster: <span className="text-slate-200">{rosterSize}</span></span>
        </div>
      </div>

      <button 
        onClick={onFinalize}
        className="group flex items-center gap-2 bg-red-900/30 hover:bg-red-600 border border-red-900/50 hover:border-red-500 text-red-200/70 hover:text-white px-3 py-1 rounded font-bold transition-all duration-200"
      >
        <FiAlertTriangle className="group-hover:animate-pulse" />
        <span>End Draft</span>
      </button>
    </div>
  );
}