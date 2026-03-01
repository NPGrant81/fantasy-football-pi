// src/components/waivers/WaiverPositionTabs.jsx
import React from 'react';
import { POSITIONS } from '@utils';
import { buttonPrimary, buttonSecondary } from '@utils/uiStandards';

/* ignore-breakpoints */

export default function WaiverPositionTabs({ activeTab, setActiveTab }) {
  const tabs = ['ALL', ...POSITIONS];

  return (
    <div className="flex gap-2 overflow-x-auto pb-4 no-scrollbar">
      {tabs.map((pos) => (
        <button
          key={pos}
          onClick={() => setActiveTab(pos)}
          className={`px-6 py-2 font-black uppercase italic ${
            activeTab === pos
              ? buttonPrimary
              : buttonSecondary
          }`}
        >
          {pos}
        </button>
      ))}
    </div>
  );
}
