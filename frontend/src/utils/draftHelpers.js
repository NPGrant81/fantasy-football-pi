// src/utils/draftHelpers.js
import { TOTAL_BUDGET, ROSTER_SIZE, POSITIONS } from './constants';

export const normalizePos = (pos) => (pos === 'TD' ? 'DEF' : pos);

export const getOwnerStats = (ownerId, history, players) => {
    const ownerPicks = history.filter(pick => pick.owner_id === ownerId);
    const spent = ownerPicks.reduce((sum, pick) => sum + pick.amount, 0);
    const budget = TOTAL_BUDGET - spent;
    const emptySpots = ROSTER_SIZE - ownerPicks.length;
    
    // The "1-Dollar Rule" calculation
    const maxBid = emptySpots > 0 ? budget - (emptySpots - 1) : 0;

    return { 
      spent, 
      budget, 
      emptySpots, 
      maxBid: Math.max(0, maxBid) 
    };
};