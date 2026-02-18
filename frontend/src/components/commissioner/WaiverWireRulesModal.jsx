import React from 'react';
import { FiActivity } from 'react-icons/fi';

export default function WaiverWireRulesModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-900 border border-green-700 rounded-xl p-8 w-full max-w-lg relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-green-400 hover:text-white">✕</button>
        <h2 className="text-2xl font-bold text-green-400 mb-4 flex items-center gap-2"><FiActivity /> Set Waiver Wire Rules</h2>
        <p className="text-slate-400 mb-4">Set rules for waiver claims, priorities, and deadlines.</p>
        {/* TODO: Add waiver wire rules form here */}
        <div className="text-center text-slate-500">Waiver wire rules form coming soon...</div>
      </div>
    </div>
  );
}
