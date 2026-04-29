import {
  DRAFT_BOARD_SORT_MODE,
  sortByDraftOrder,
  sortByPosition,
  sortByValue,
  sortPlayersForMode,
} from '../src/utils/draftBoardSort';

describe('draft board sorting utility', () => {
  test('sortByDraftOrder prioritizes draft pick number then player name', () => {
    const players = [
      { player_name: 'Zeta RB', draft_pick_number: 5, __historyIndex: 0 },
      { player_name: 'Alpha QB', draft_pick_number: 2, __historyIndex: 1 },
      { player_name: 'Beta WR', draft_pick_number: 5, __historyIndex: 2 },
    ];

    const names = sortByDraftOrder(players).map((player) => player.player_name);
    expect(names).toEqual(['Alpha QB', 'Beta WR', 'Zeta RB']);
  });

  test('sortByValue sorts high to low with position and name fallback', () => {
    const players = [
      { player_name: 'Zulu WR', amount: 30, position: 'WR', __historyIndex: 0 },
      { player_name: 'Alpha QB', amount: 30, position: 'QB', __historyIndex: 1 },
      { player_name: 'Beta QB', amount: 40, position: 'QB', __historyIndex: 2 },
      { player_name: 'Gamma QB', amount: 30, position: 'QB', __historyIndex: 3 },
    ];

    const names = sortByValue(players).map((player) => player.player_name);
    expect(names).toEqual(['Beta QB', 'Alpha QB', 'Gamma QB', 'Zulu WR']);
  });

  test('sortByPosition uses fixed position rank then player name', () => {
    const players = [
      { player_name: 'Mike TE', position: 'TE', __historyIndex: 0 },
      { player_name: 'Aaron WR', position: 'WR', __historyIndex: 1 },
      { player_name: 'Zane WR', position: 'WR', __historyIndex: 2 },
      { player_name: 'Baker QB', position: 'QB', __historyIndex: 3 },
    ];

    const names = sortByPosition(players).map((player) => player.player_name);
    expect(names).toEqual(['Baker QB', 'Aaron WR', 'Zane WR', 'Mike TE']);
  });

  test('sortPlayersForMode keeps deterministic order for fully tied players', () => {
    const players = [
      { player_name: 'Same Name', amount: 20, position: 'RB', __historyIndex: 2 },
      { player_name: 'Same Name', amount: 20, position: 'RB', __historyIndex: 1 },
      { player_name: 'Same Name', amount: 20, position: 'RB', __historyIndex: 3 },
    ];

    const historyIndexes = sortPlayersForMode(players, DRAFT_BOARD_SORT_MODE.VALUE_DESC).map(
      (player) => player.__historyIndex
    );

    expect(historyIndexes).toEqual([1, 2, 3]);
  });
});
