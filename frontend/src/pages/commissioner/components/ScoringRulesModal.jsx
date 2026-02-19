import React from 'react';
import { FiSettings } from 'react-icons/fi';

export default function ScoringRulesModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-900 border border-purple-700 rounded-xl p-8 w-full max-w-lg relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-purple-400 hover:text-white"
        >
          ✕
        </button>
        <h2 className="text-2xl font-bold text-purple-400 mb-4 flex items-center gap-2">
          <FiSettings /> Set Scoring Rules
        </h2>
        <p className="text-slate-400 mb-4">
          Configure how points are awarded for all league actions.
        </p>
        <div className="text-center text-slate-500">
          Scoring rules form coming soon...
        </div>
      </div>
    </div>
  );
}
