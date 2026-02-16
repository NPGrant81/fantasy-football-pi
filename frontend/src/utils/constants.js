// src/utils/constants.js
export const TOTAL_BUDGET = 200;
export const ROSTER_SIZE = 14;
export const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

// Standard roster requirements for validation
export const ROSTER_REQUIREMENTS = {
  QB: 1,
  RB: 2,
  WR: 2,
  TE: 1,
  FLEX: 1,
  K: 1,
  DEF: 1,
  BENCH: 5
};