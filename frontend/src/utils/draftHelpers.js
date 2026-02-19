// src/utils/draftHelpers.js
import { TOTAL_BUDGET, ROSTER_SIZE } from './constants';

// --- 1.1 DATA NORMALIZATION ---
export const normalizePos = (pos) => (pos === 'TD' ? 'DEF' : pos);



// --- 1.3 CALCULATION ENGINE ---
export const getOwnerStats = (ownerId, history, budgets = {}, fallbackBudget = TOTAL_BUDGET) => {
  const ownerPicks = history.filter((pick) => pick.owner_id === ownerId);
  const spent = ownerPicks.reduce((sum, pick) => sum + pick.amount, 0);
  const totalBudget = budgets[ownerId] ?? fallbackBudget;
  const budget = totalBudget - spent;
  const emptySpots = ROSTER_SIZE - ownerPicks.length;

  // 1.3.1 The "1-Dollar Rule" logic
  const maxBid = emptySpots > 0 ? budget - (emptySpots - 1) : 0;

  return {
    spent,
    budget,
    emptySpots,
    maxBid: Math.max(0, maxBid),
    isFull: emptySpots <= 0,
  };
};
