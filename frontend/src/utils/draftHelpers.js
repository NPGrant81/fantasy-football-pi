export const ROSTER_SIZE = 14;
export const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

export const normalizePos = (pos) => (pos === 'TD' ? 'DEF' : pos);

export const getOwnerStats = (ownerId, history, players) => {
    const ownerPicks = history.filter(pick => pick.owner_id === ownerId);
    const spent = ownerPicks.reduce((sum, pick) => sum + pick.amount, 0);
    const remaining = 200 - spent;
    const emptySpots = ROSTER_SIZE - ownerPicks.length;
    // Auction logic: must save at least $1 for every remaining spot
    const maxBid = emptySpots > 0 ? remaining - (emptySpots - 1) : 0;

    return { spent, remaining, emptySpots, maxBid };
};