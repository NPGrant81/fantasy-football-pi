import React, { useState } from 'react';

const ScoringCard = ({ title, fields }) => (
  <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg dark:bg-slate-900 dark:border-slate-800">
    <h3 className="text-slate-900 font-bold mb-4 border-b border-slate-200 pb-2 dark:text-white dark:border-slate-800">
      {title}
    </h3>
    {fields.map((field) => (
      <div key={field} className="flex justify-between items-center mb-3">
        <span className="text-sm text-slate-600 dark:text-slate-400">{field.split(' ')[0]}</span>
        <input
          type="number"
          className="w-20 bg-white border border-slate-300 rounded p-1 text-right text-blue-600 text-sm dark:bg-black dark:border-slate-700 dark:text-cyan-400"
          placeholder="0"
        />
      </div>
    ))}
  </div>
);

export default function AdminSettings() {
  const [activeTab, setActiveTab] = useState('scoring');

  const tabs = [
    { id: 'league', label: 'League Prep' },
    { id: 'roster', label: 'Roster Rules' },
    { id: 'scoring', label: 'Scoring Rules' },
    { id: 'data', label: 'Data Management' },
  ];

  return (
    <div className="flex flex-col h-full bg-white border border-slate-200 rounded-lg shadow-2xl dark:bg-[#05070a] dark:border-slate-800">
      {/* Tab Navigation */}
      <div className="flex border-b border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900/50">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-6 py-4 text-xs font-bold uppercase tracking-widest transition-all ${
              activeTab === tab.id
                ? 'text-blue-600 border-b-2 border-blue-600 bg-white dark:text-cyan-400 dark:border-cyan-400 dark:bg-slate-800'
                : 'text-slate-500 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content Area */}
      <div className="p-6 overflow-y-auto custom-scrollbar">
        {activeTab === 'scoring' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-fadeIn">
            <ScoringCard
              title="Passing"
              fields={['TD (4pt)', 'Yard (0.04)', 'INT (-2)']}
            />
            <ScoringCard
              title="Rushing"
              fields={['TD (6pt)', 'Yard (0.1)', 'Fumble (-2)']}
            />
          </div>
        )}

        {activeTab === 'data' && (
          <div className="space-y-4">
            <div className="p-4 bg-slate-100 rounded border border-slate-300 dark:bg-slate-800 dark:border-slate-700">
              <h3 className="text-blue-600 font-bold mb-2 dark:text-cyan-400">NFL Data Refresh</h3>
              <p className="text-xs text-slate-600 mb-4 dark:text-slate-400">
                Syncs latest rosters and projections. Existing data will be
                updated, not duplicated.
              </p>
              <button className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded text-sm font-bold dark:bg-cyan-600 dark:hover:bg-cyan-500">
                Run Regen Script
              </button>
            </div>
          </div>
        )}

        {activeTab === 'league' && (
          <div>
            <p className="text-slate-600 dark:text-slate-400">League preparation tools go here.</p>
          </div>
        )}

        {activeTab === 'roster' && (
          <div>
            <p className="text-slate-600 dark:text-slate-400">Roster & Lineup rules.</p>
          </div>
        )}
      </div>
    </div>
  );
}
