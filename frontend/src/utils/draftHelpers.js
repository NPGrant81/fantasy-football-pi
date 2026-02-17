// src/utils/draftHelpers.js
import { TOTAL_BUDGET, ROSTER_SIZE } from './constants';

// --- 1.1 DATA NORMALIZATION ---
export const normalizePos = (pos) => (pos === 'TD' ? 'DEF' : pos);

// --- 1.2 VISUAL MAPPING (Salvaged from uiHelpers) ---
export const getPosColor = (rawPos) => {
    const pos = normalizePos(rawPos);
    // 1.2.1 Object Lookup: Faster and easier to read than if/else
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

// --- 1.3 CALCULATION ENGINE ---
export const getOwnerStats = (ownerId, history) => {
    const ownerPicks = history.filter(pick => pick.owner_id === ownerId);
    const spent = ownerPicks.reduce((sum, pick) => sum + pick.amount, 0);
    const budget = TOTAL_BUDGET - spent;
    const emptySpots = ROSTER_SIZE - ownerPicks.length;
    
    // 1.3.1 The "1-Dollar Rule" logic
    const maxBid = emptySpots > 0 ? budget - (emptySpots - 1) : 0;

    return { 
      spent, 
      budget, 
      emptySpots, 
      maxBid: Math.max(0, maxBid),
      isFull: emptySpots <= 0
    };
};