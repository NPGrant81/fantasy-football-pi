// src/components/waivers/WaiverPositionTabs.jsx
import React from 'react';
import { POSITIONS } from '@utils';
import { bgColors, textColors, borderColors } from '../../utils/uiHelpers';

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
              ? `${bgColors.warning} ${borderColors.warning} text-black shadow-[0_0_15px_rgba(234,179,8,0.3)]`
              : `${bgColors.main} ${borderColors.main} ${textColors.secondary} hover:${borderColors.main} hover:${textColors.main}`
          }`}
        >
          {pos}
        </button>
      ))}
    </div>
  );
}
