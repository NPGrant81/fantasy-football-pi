import { swapPlayers } from '../src/utils/rosterHelpers';

describe('swapPlayers helper', () => {
  it('swaps two filled slots', () => {
    const roster = [{ id: 1 }, { id: 2 }, { id: 3 }];
    const result = swapPlayers(roster, 0, 2);
    expect(result.map((p) => p?.id)).toEqual([3, 2, 1]);
  });

  it('moves player into empty slot', () => {
    const roster = [{ id: 1 }, null, { id: 3 }];
    const result = swapPlayers(roster, 2, 1);
    expect(result[0]?.id).toBe(1);
    expect(result[1]?.id).toBe(3);
    expect(result[2]).toBeNull();
  });

  it('returns new array without mutating original', () => {
    const roster = [{ id: 1 }, { id: 2 }];
    const result = swapPlayers(roster, 0, 1);
    expect(roster[0].id).toBe(1);
    expect(result[0].id).toBe(2);
  });
});
