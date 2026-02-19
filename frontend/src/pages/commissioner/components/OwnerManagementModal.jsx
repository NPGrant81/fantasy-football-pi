import React from 'react';
import { FiUsers } from 'react-icons/fi';

export default function OwnerManagementModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-900 border border-blue-700 rounded-xl p-8 w-full max-w-lg relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-blue-400 hover:text-white"
        >
          ✕
        </button>
        <h2 className="text-2xl font-bold text-blue-400 mb-4 flex items-center gap-2">
          <FiUsers /> Invite/Manage Team Owners
        </h2>
        <p className="text-slate-400 mb-4">
          Invite new owners, manage teams, and verify league access.
        </p>
        <div className="text-center text-slate-500">
          Owner management form coming soon...
        </div>
      </div>
    </div>
  );
}
