// src/components/waivers/DropPlayerModal.jsx
import React from 'react';
import { getPosColor } from '../../utils/uiHelpers';
import {
  buttonSecondary,
  modalDescription,
  modalOverlay,
  modalSurface,
  modalTitle,
} from '@utils/uiStandards';

export default function DropPlayerModal({
  isOpen,
  onClose,
  myRoster,
  onConfirm,
}) {
  // 1. If the modal isn't open, don't render anything
  if (!isOpen) return null;

  return (
    <div className={modalOverlay}>
      <div className={`${modalSurface} sm:max-w-md`}>
        {/* 2. Header: Explain why they are here */}
        <h2 className={modalTitle}>Roster Full!</h2>
        <p className={`${modalDescription} mb-6`}>
          Select a player to release to make room for your new addition.
        </p>

        <div className="space-y-3 max-h-60 overflow-y-auto pr-2 custom-scrollbar">
          {myRoster.map((player) => (
            <button
              key={player.id}
              onClick={() => onConfirm(player.id)}
              className="group flex w-full items-center justify-between rounded-2xl border border-slate-300 bg-white p-4 transition-all hover:border-red-500/50 hover:bg-red-50 dark:border-slate-800 dark:bg-slate-950 dark:hover:bg-red-900/10"
            >
              {/* 3. Player Info: Position and Name */}
              <div className="flex items-center gap-3">
                <span
                  className={`text-[9px] font-black px-2 py-1 rounded ${getPosColor(player.position)}`}
                >
                  {player.position}
                </span>
                <span className="font-bold text-slate-900 group-hover:text-red-500 dark:text-white dark:group-hover:text-red-400">
                  {player.name}
                </span>
              </div>
              <span className="text-[10px] font-black uppercase italic text-slate-600 group-hover:text-red-500 dark:text-slate-400 dark:group-hover:text-red-400">
                Drop
              </span>
            </button>
          ))}
        </div>

        {/* 4. Action: Allow user to back out */}
        <button onClick={onClose} className={`${buttonSecondary} mt-6 w-full`}>
          Cancel Claim
        </button>
      </div>
    </div>
  );
}
