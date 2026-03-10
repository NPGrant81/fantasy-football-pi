import {
  BENCH_MULTIPLIER,
  buildCashRecommendation,
  computeLineupAdjustedValue,
  computePlayerValue,
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
