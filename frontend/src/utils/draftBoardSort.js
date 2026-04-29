export const POSITION_RANK = {
  QB: 1,
  RB: 2,
  WR: 3,
  TE: 4,
  K: 5,
  DEF: 6,
};

export const DRAFT_BOARD_SORT_MODE = {
  DRAFT_ORDER: 'draft_order',
  VALUE_DESC: 'value_desc',
  POSITION: 'position',
};

const toNumber = (value, fallback = Number.NaN) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const toTimestamp = (value) => {
  const ts = new Date(value || '').getTime();
  return Number.isFinite(ts) ? ts : Number.NaN;
};

const getPlayerName = (player) => String(player?.player_name || player?.name || '').trim();

const getDraftOrder = (player) => {
  const numericOrder = toNumber(
    player?.draft_pick_number ??
      player?.draftPickNumber ??
      player?.pick_number ??
      player?.pick_number_overall,
    Number.NaN
  );
  if (Number.isFinite(numericOrder)) return numericOrder;

  const timestampOrder = toTimestamp(
    player?.draft_timestamp ?? player?.draftTimestamp ?? player?.timestamp
  );
  if (Number.isFinite(timestampOrder)) return timestampOrder;

  return Number.POSITIVE_INFINITY;
};

const getValuePaid = (player) =>
  toNumber(
    player?.amount ?? player?.price ?? player?.draft_value ?? player?.draftValue,
    Number.NEGATIVE_INFINITY
  );

const getPositionRank = (player) => {
  const position = String(player?.position || player?.pos || '').toUpperCase();
  return POSITION_RANK[position] ?? 99;
};

const compareName = (a, b) => getPlayerName(a).localeCompare(getPlayerName(b));

const compareStableIndex = (a, b) =>
  toNumber(a?.__historyIndex, Number.MAX_SAFE_INTEGER) -
  toNumber(b?.__historyIndex, Number.MAX_SAFE_INTEGER);

export function sortByDraftOrder(players = []) {
  return [...players].sort((a, b) => {
    const orderDiff = getDraftOrder(a) - getDraftOrder(b);
    if (orderDiff !== 0) return orderDiff;

    const nameDiff = compareName(a, b);
    if (nameDiff !== 0) return nameDiff;

    return compareStableIndex(a, b);
  });
}

export function sortByValue(players = []) {
  return [...players].sort((a, b) => {
    const valueDiff = getValuePaid(b) - getValuePaid(a);
    if (valueDiff !== 0) return valueDiff;

    const rankDiff = getPositionRank(a) - getPositionRank(b);
    if (rankDiff !== 0) return rankDiff;

    const nameDiff = compareName(a, b);
    if (nameDiff !== 0) return nameDiff;

    return compareStableIndex(a, b);
  });
}

export function sortByPosition(players = []) {
  return [...players].sort((a, b) => {
    const rankDiff = getPositionRank(a) - getPositionRank(b);
    if (rankDiff !== 0) return rankDiff;

    const nameDiff = compareName(a, b);
    if (nameDiff !== 0) return nameDiff;

    return compareStableIndex(a, b);
  });
}

export function sortPlayersForMode(players = [], mode = DRAFT_BOARD_SORT_MODE.DRAFT_ORDER) {
  switch (mode) {
    case DRAFT_BOARD_SORT_MODE.VALUE_DESC:
      return sortByValue(players);
    case DRAFT_BOARD_SORT_MODE.POSITION:
      return sortByPosition(players);
    case DRAFT_BOARD_SORT_MODE.DRAFT_ORDER:
    default:
      return sortByDraftOrder(players);
  }
}
