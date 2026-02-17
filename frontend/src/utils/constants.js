// src/utils/constants.js

// --- 1.1 ECONOMIC CONSTRAINTS ---
export const TOTAL_BUDGET = 200;
export const MIN_BID = 1;

// --- 1.2 ROSTER CONSTRAINTS ---
export const ROSTER_SIZE = 14;
export const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

// 1.2.1 Standard roster requirements for validation logic
export const ROSTER_REQUIREMENTS = {
  QB: 1,
  RB: 2,
  WR: 2,
  TE: 1,
  FLEX: 1,
  K: 1,
  DEF: 1,
  BENCH: 5,
};

// --- 1.3 SYSTEM LIMITS ---
export const MAX_SUGGESTIONS = 8;
export const POLL_INTERVAL = 3000; // 3 seconds for Pi-friendly polling
