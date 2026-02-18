// src/utils/uiHelpers.js

// --- 1.1 GENERAL COLOR UTILITIES ---
export const getPosColor = (rawPos) => {
  const pos = rawPos === 'TD' ? 'DEF' : rawPos;
  const colors = {
    QB: 'text-red-400 border-red-900/50 bg-red-900/10',
    RB: 'text-green-400 border-green-900/50 bg-green-900/10',
    WR: 'text-blue-400 border-blue-900/50 bg-blue-900/10',
    TE: 'text-orange-400 border-orange-900/50 bg-orange-900/10',
    K: 'text-purple-400 border-purple-900/50 bg-purple-900/10',
    DEF: 'text-slate-400 border-slate-600 bg-slate-800',
  };
  return colors[pos] || 'text-gray-400 border-gray-700 bg-slate-900';
};

// --- 1.2 COMMON TAILWIND COLOR CLASSES ---
export const bgColors = {
  main: 'bg-slate-900',
  card: 'bg-slate-950',
  header: 'bg-slate-950/50',
  section: 'bg-slate-950/20',
  accent: 'bg-blue-600',
  warning: 'bg-yellow-500',
  error: 'bg-red-500',
};

export const textColors = {
  main: 'text-white',
  secondary: 'text-slate-400',
  accent: 'text-blue-600',
  warning: 'text-yellow-500',
  error: 'text-red-500',
};

export const borderColors = {
  main: 'border-slate-800',
  accent: 'border-blue-500',
  warning: 'border-yellow-500',
  error: 'border-red-500',
};

export const menuGradients = {
  draft: 'bg-gradient-to-r from-yellow-600 to-yellow-500',
  team: 'bg-gradient-to-r from-green-700 to-green-600',
  matchups: 'bg-gradient-to-r from-red-700 to-red-600',
  waivers: 'bg-gradient-to-r from-blue-700 to-blue-600',
};

// --- 1.3 Utility for combining classes ---
export const combineClasses = (...classes) => classes.filter(Boolean).join(' ');
