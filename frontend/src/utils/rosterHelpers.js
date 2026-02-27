// utility functions used by LockerRoom / roster engine

/**
 * Swap two entries in the roster array and return a new array.
 * If target index is empty (undefined), the dragged player simply moves.
 * If both indices contain players, their positions are swapped exactly,
 * preserving order of the rest of the array.  This mirrors the drag-drop
 * behaviour described in the sprint spec.
 *
 * @param {Array} roster - array of player objects
 * @param {number} fromIdx - index of dragged player
 * @param {number} toIdx - index of drop target
 * @returns {Array} new roster
 */
export function swapPlayers(roster, fromIdx, toIdx) {
  const newRoster = [...roster];
  const dragged = newRoster[fromIdx];
  newRoster[fromIdx] = newRoster[toIdx] || null;
  newRoster[toIdx] = dragged;
  return newRoster;
}
