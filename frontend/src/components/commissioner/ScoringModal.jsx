import React from 'react';
import { FiX, FiSave } from 'react-icons/fi';

export default function ScoringModal({ open, onClose, settings, onChange, onSave, activeTab, setActiveTab }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="bg-slate-900 rounded-2xl shadow-2xl p-8 w-full max-w-2xl relative">
        <button
          className="absolute top-4 right-4 text-slate-400 hover:text-white"
          onClick={onClose}
        >
          <FiX size={24} />
        </button>
        <h2 className="text-2xl font-black mb-6 text-white">Edit Scoring Rules</h2>
        <div className="flex gap-4 mb-6">
          {settings?.scoring_rules?.map((rule, idx) => (
            <button
              key={rule.category}
              className={`px-4 py-2 rounded-lg font-bold uppercase text-xs ${activeTab === rule.category ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300'}`}
              onClick={() => setActiveTab(rule.category)}
            >
              {rule.category}
            </button>
          ))}
        </div>
        <div className="space-y-4">
          {settings?.scoring_rules?.filter(r => r.category === activeTab).map((rule, idx) => (
            <div key={idx} className="flex flex-col gap-2 bg-slate-800 p-4 rounded-lg">
              <label className="font-bold text-slate-300">{rule.name}</label>
              <input
                type="number"
                className="p-2 rounded bg-slate-900 text-white border border-slate-700"
                value={rule.value}
                onChange={e => onChange(idx, 'value', e.target.value)}
              />
            </div>
          ))}
        </div>
        <button
          className="mt-8 w-full bg-green-600 hover:bg-green-500 text-black py-3 rounded-lg font-black uppercase flex items-center justify-center gap-2"
          onClick={onSave}
        >
          <FiSave /> Save Scoring
        </button>
      </div>
    </div>
  );
}
