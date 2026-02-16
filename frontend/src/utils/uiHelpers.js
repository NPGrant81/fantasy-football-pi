// src/utils/uiHelpers.js
import { normalizePos } from './draftHelpers';

export const getPosColor = (rawPos) => {
  const pos = normalizePos(rawPos);
  const colors = {
    QB: 'text-red-400 border-red-900/50 bg-red-900/10',
    RB: 'text-green-400 border-green-900/50 bg-green-900/10',
    WR: 'text-blue-400 border-blue-900/50 bg-blue-900/10',
    TE: 'text-orange-400 border-orange-900/50 bg-orange-900/10',
    K: 'text-purple-400 border-purple-900/50 bg-purple-900/10',
    DEF: 'text-slate-400 border-slate-600 bg-slate-800',
  };
  return colors[pos] || 'text-gray-400 border-gray-700';
};