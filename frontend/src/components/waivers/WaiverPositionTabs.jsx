// src/components/waivers/WaiverPositionTabs.jsx
import React from 'react';
import { POSITIONS } from '@utils';

export default function WaiverPositionTabs({ activeTab, setActiveTab }) {
  const tabs = ['ALL', ...POSITIONS];

  return (
    <div className="flex gap-2 overflow-x-auto pb-4 no-scrollbar">
      {tabs.map((pos) => (
        <button
          key={pos}
          onClick={() => setActiveTab(pos)}
          className={`px-6 py-2 rounded-xl font-black uppercase italic transition-all duration-200 border-2 ${
            activeTab === pos
              ? 'bg-yellow-500 border-yellow-500 text-black shadow-[0_0_15px_rgba(234,179,8,0.3)]'
              : 'bg-slate-900 border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-300'
          }`}
        >
          {pos}
        </button>
      ))}
    </div>
  );
}
