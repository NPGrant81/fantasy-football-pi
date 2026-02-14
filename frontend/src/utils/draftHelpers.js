// frontend/src/utils/draftHelpers.js

export const ROSTER_SIZE = 14;
export const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

// NOTICE THE WORD "export" HERE
export const normalizePos = (pos) => (pos === 'TD' ? 'DEF' : pos);

// AND HERE
export const getPosColor = (rawPos) => {
  const pos = normalizePos(rawPos)
  switch (pos) {
    case 'QB': return 'text-red-400 border-red-900/50 bg-red-900/10'
    case 'RB': return 'text-green-400 border-green-900/50 bg-green-900/10'
    case 'WR': return 'text-blue-400 border-blue-900/50 bg-blue-900/10'
    case 'TE': return 'text-orange-400 border-orange-900/50 bg-orange-900/10'
    case 'K': return 'text-purple-400 border-purple-900/50 bg-purple-900/10'
    case 'DEF': return 'text-slate-400 border-slate-600 bg-slate-800'
    default: return 'text-gray-400 border-gray-700'
  }
};

// AND HERE
export const getOwnerStats = (ownerId, history, players) => {
    const ownerPicks = history.filter(pick => pick.owner_id === ownerId);
    const spent = ownerPicks.reduce((sum, pick) => sum + pick.amount, 0);
    const remaining = 200 - spent;
    const emptySpots = ROSTER_SIZE - ownerPicks.length;
    const maxBid = emptySpots > 0 ? remaining - (emptySpots - 1) : 0;

    const posCounts = {};
    POSITIONS.forEach(pos => posCounts[pos] = 0);
    
    ownerPicks.forEach(pick => {
        const p = players.find(pl => pl.id === pick.player_id);
        if (p) {
            const normPos = normalizePos(p.position);
            if (posCounts[normPos] !== undefined) posCounts[normPos]++;
        }
    });

    return { spent, remaining, emptySpots, maxBid, posCounts };
};