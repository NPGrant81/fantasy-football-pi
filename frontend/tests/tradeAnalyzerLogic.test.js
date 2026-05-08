import {
  BENCH_MULTIPLIER,
  buildCashRecommendation,
  computeNetLineupImpact,
  computeLineupAdjustedValue,
  computeOutgoingLossWithReplacement,
  computePlayerValue,
  deriveTrendAdjustment,
  deriveVolatilityPenalty,
  deriveRiskPenalty,
  gradeForDelta,
  normalizePosition,
  summarizeTradeSide,
} from '../src/components/charts/tradeAnalyzerLogic';

describe('tradeAnalyzerLogic', () => {
  test('normalizes DEF to DST', () => {
    expect(normalizePosition('DEF')).toBe('DST');
    expect(normalizePosition('wr')).toBe('WR');
  });

  test('computes base value from ros/trend/volatility/risk', () => {
    const value = computePlayerValue({
      ros_projection: 20,
      trend_adjustment: 2,
      volatility_penalty: 1,
      risk_penalty: 1,
    });
    expect(value).toBe(20);
  });

  test('bench lineup value applies multiplier', () => {
    const starter = computeLineupAdjustedValue({ projected_points: 15, is_starter: true });
    const bench = computeLineupAdjustedValue({ projected_points: 15, is_starter: false });
    expect(starter).toBe(15);
    expect(bench).toBe(Number((15 * BENCH_MULTIPLIER).toFixed(2)));
  });

  test('summarizes side values deterministically', () => {
    const total = summarizeTradeSide([
      { projected_points: 18, is_starter: true },
      { projected_points: 10, is_starter: false },
    ]);
    expect(total).toBe(24);
  });

  test('computes outgoing starter loss with bench replacement delta', () => {
    const outgoing = [
      { player_id: 1, position: 'RB', projected_points: 18, is_starter: true },
    ];
    const roster = [
      ...outgoing,
      { player_id: 2, position: 'RB', projected_points: 10, is_starter: false },
    ];

    const loss = computeOutgoingLossWithReplacement(outgoing, roster);
    expect(loss).toBe(8);
  });

  test('computes outgoing bench loss as bench-adjusted value', () => {
    const outgoing = [
      { player_id: 3, position: 'WR', projected_points: 15, is_starter: false },
    ];
    const loss = computeOutgoingLossWithReplacement(outgoing, outgoing);
    expect(loss).toBe(Number((15 * BENCH_MULTIPLIER).toFixed(2)));
  });

  test('uses each replacement at most once across multiple starters', () => {
    const outgoing = [
      { player_id: 1, position: 'RB', projected_points: 20, is_starter: true },
      { player_id: 2, position: 'RB', projected_points: 18, is_starter: true },
    ];
    const roster = [
      ...outgoing,
      { player_id: 3, position: 'RB', projected_points: 12, is_starter: false },
      { player_id: 4, position: 'RB', projected_points: 9, is_starter: false },
    ];

    const loss = computeOutgoingLossWithReplacement(outgoing, roster);
    expect(loss).toBe(17);
  });

  test('starter replacement assignment is stable regardless of outgoing order', () => {
    const outgoingA = [
      { player_id: 10, position: 'WR', projected_points: 12, is_starter: true },
      { player_id: 11, position: 'WR', projected_points: 20, is_starter: true },
    ];
    const outgoingB = [...outgoingA].reverse();
    const roster = [
      ...outgoingA,
      { player_id: 12, position: 'WR', projected_points: 15, is_starter: false },
      { player_id: 13, position: 'WR', projected_points: 5, is_starter: false },
    ];

    const lossA = computeOutgoingLossWithReplacement(outgoingA, roster);
    const lossB = computeOutgoingLossWithReplacement(outgoingB, roster);
    expect(lossA).toBe(12);
    expect(lossB).toBe(12);
  });

  test('computes net lineup impact using incoming gain minus replacement-aware loss', () => {
    const incoming = [
      { player_id: 11, position: 'RB', projected_points: 16, is_starter: true },
    ];
    const outgoing = [
      { player_id: 1, position: 'RB', projected_points: 18, is_starter: true },
    ];
    const roster = [
      ...outgoing,
      { player_id: 2, position: 'RB', projected_points: 10, is_starter: false },
    ];

    const net = computeNetLineupImpact({
      incomingPlayers: incoming,
      outgoingPlayers: outgoing,
      fullRoster: roster,
    });
    expect(net).toBe(8);
  });

  test('grade mapping handles balanced trade', () => {
    expect(gradeForDelta(1)).toEqual(['A', 'A']);
  });

  test('grade mapping handles slight team A advantage', () => {
    expect(gradeForDelta(4)).toEqual(['A', 'B']);
  });

  test('grade mapping handles moderate team B advantage', () => {
    expect(gradeForDelta(-8)).toEqual(['C', 'B']);
  });

  test('cash recommendation null at threshold', () => {
    expect(buildCashRecommendation(10)).toBeNull();
    expect(buildCashRecommendation(-10)).toBeNull();
  });

  test('cash recommendation slight tier above threshold', () => {
    const rec = buildCashRecommendation(12);
    expect(rec.tier).toBe('Slightly Unbalanced');
    expect(rec.amount).toBe(Math.round(12 * 0.45));
  });

  test('cash recommendation moderate and high tiers', () => {
    const moderate = buildCashRecommendation(20);
    const high = buildCashRecommendation(30);
    expect(moderate.tier).toBe('Moderately Unbalanced');
    expect(high.tier).toBe('Highly Unbalanced');
    expect(high.amount).toBe(Math.round(30 * 0.75));
  });
});

// ─── Issue #153: Valuation Model Spec Compliance ────────────────────────────
describe('valuation model spec compliance (issue #153)', () => {
  test('trend coefficient T=0.35 applied to raw last_3/season_avg inputs', () => {
    const adj = deriveTrendAdjustment({
      last_3_avg_points: 18,
      season_avg_points: 14,
    });
    expect(adj).toBeCloseTo((18 - 14) * 0.35, 5);
  });

  test('trend passes through pre-computed trend_adjustment', () => {
    expect(deriveTrendAdjustment({ trend_adjustment: 2.5 })).toBeCloseTo(2.5, 5);
  });

  test('volatility coefficient V=0.20 applied to points_stddev', () => {
    const penalty = deriveVolatilityPenalty({ points_stddev: 5 });
    expect(penalty).toBeCloseTo(5 * 0.20, 5);
  });

  test('volatility passes through pre-computed volatility_penalty', () => {
    expect(deriveVolatilityPenalty({ volatility_penalty: 1.2 })).toBeCloseTo(1.2, 5);
  });

  test('risk coefficient R=1.5 applied to risk_score', () => {
    const penalty = deriveRiskPenalty({ risk_score: 3 });
    expect(penalty).toBeCloseTo(3 * 1.5, 5);
  });

  test('risk passes through pre-computed risk_penalty', () => {
    expect(deriveRiskPenalty({ risk_penalty: 4.5 })).toBeCloseTo(4.5, 5);
  });

  test('combined formula: ROS + trend - volatility - risk', () => {
    const value = computePlayerValue({
      ros_projection: 20,
      last_3_avg_points: 18,
      season_avg_points: 14,
      points_stddev: 5,
      risk_score: 2,
    });
    const expectedTrend = (18 - 14) * 0.35;
    const expectedVol = 5 * 0.20;
    const expectedRisk = 2 * 1.5;
    expect(value).toBeCloseTo(20 + expectedTrend - expectedVol - expectedRisk, 2);
  });

  test('bench multiplier is 0.6 (spec §6)', () => {
    expect(BENCH_MULTIPLIER).toBe(0.6);
  });

  test('balanced trade produces no cash recommendation (delta ≤ 10)', () => {
    expect(buildCashRecommendation(10)).toBeNull();
    expect(buildCashRecommendation(-10)).toBeNull();
  });

  test('cash tiers driven from config — amounts scale correctly', () => {
    const slight = buildCashRecommendation(13);
    const moderate = buildCashRecommendation(20);
    const high = buildCashRecommendation(30);
    expect(slight.tier).toBe('Slightly Unbalanced');
    expect(moderate.tier).toBe('Moderately Unbalanced');
    expect(high.tier).toBe('Highly Unbalanced');
    expect(slight.amount).toBe(Math.round(13 * 0.45));
    expect(moderate.amount).toBe(Math.round(20 * 0.60));
    expect(high.amount).toBe(Math.round(30 * 0.75));
  });
});
