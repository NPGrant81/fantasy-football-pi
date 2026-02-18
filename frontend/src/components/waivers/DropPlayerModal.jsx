// src/components/waivers/DropPlayerModal.jsx
import React from 'react';
import { getPosColor } from '../utils/uiHelpers';

export default function DropPlayerModal({
  isOpen,
  onClose,
  myRoster,
  onConfirm,
}) {
  // 1. If the modal isn't open, don't render anything
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-800 w-full max-w-md rounded-[2.5rem] p-8 shadow-2xl">
        {/* 2. Header: Explain why they are here */}
        <h2 className="text-2xl font-black uppercase italic text-white mb-2">
          Roster Full!
        </h2>
        <p className="text-slate-400 text-sm mb-6">
          Select a player to release to make room for your new addition.
        </p>

        <div className="space-y-3 max-h-60 overflow-y-auto pr-2 custom-scrollbar">
          {myRoster.map((player) => (
            <button
              key={player.id}
              onClick={() => onConfirm(player.id)}
              className="w-full flex justify-between items-center p-4 bg-slate-950 border border-slate-800 rounded-2xl hover:border-red-500/50 hover:bg-red-900/10 transition-all group"
            >
              {/* 3. Player Info: Position and Name */}
              <div className="flex items-center gap-3">
                <span
                  className={`text-[9px] font-black px-2 py-1 rounded ${getPosColor(player.position)}`}
                >
                  {player.position}
                </span>
                <span className="text-white font-bold group-hover:text-red-400">
                  {player.name}
                </span>
              </div>
              <span className="text-[10px] font-black text-slate-600 uppercase italic group-hover:text-red-500">
                Drop
              </span>
            </button>
          ))}
        </div>

        {/* 4. Action: Allow user to back out */}
        <button
          onClick={onClose}
          className="w-full mt-6 py-3 text-slate-500 font-bold hover:text-white transition"
        >
          Cancel Claim
        </button>
      </div>
    </div>
  );
}
