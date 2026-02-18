import React from 'react';
import { FiShield } from 'react-icons/fi';

export default function TradeRulesModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-900 border border-yellow-700 rounded-xl p-8 w-full max-w-lg relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-yellow-400 hover:text-white">✕</button>
        <h2 className="text-2xl font-bold text-yellow-400 mb-4 flex items-center gap-2"><FiShield /> Set Trade Rules</h2>
        <p className="text-slate-400 mb-4">Configure trade review, veto, and deadlines.</p>
        {/* TODO: Add trade rules form here */}
        <div className="text-center text-slate-500">Trade rules form coming soon...</div>
      </div>
    </div>
  );
}
