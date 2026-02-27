import rosterData from '../src/mock/uat_roster.json';
import matchupData from '../src/mock/uat_matchup.json';
import projActual from '../src/mock/uat_proj_actual.json';
import { POSITION_COLORS } from '@/constants/ui';

describe('UAT mock fixtures sanity', () => {
  test('roster JSON structure is valid', () => {
    expect(rosterData.test_case).toBe('Locker Room Optimization Check');
    expect(Array.isArray(rosterData.roster)).toBe(true);
    const wr2 = rosterData.roster.find(r => r.slot === 'WR2');
    expect(wr2).toBeDefined();
    expect(wr2.better_option_available.name).toBe('Puka Nacua');
    // ensure color mapping exists for WR
    expect(POSITION_COLORS.WR).toBeDefined();
  });

  test('matchup JSON totals match player scores', () => {
    const calcTotal = team => team.players.reduce((sum,p) => sum + p.score, 0);
    expect(calcTotal(matchupData.home_team)).toBeCloseTo(matchupData.home_team.total_score);
    expect(calcTotal(matchupData.away_team)).toBeCloseTo(matchupData.away_team.total_score);
  });

  test('projected vs actual fixture assigns recommendation correctly', () => {
    expect(projActual.scenario).toBe('StartSitCheck');
    projActual.players.forEach((p, idx, arr) => {
      const highestProj = Math.max(...arr.map(x => x.projected_points));
      if (p.projected_points === highestProj) {
        expect(p.is_recommended).toBe(true);
      } else {
        expect(p.is_recommended).toBe(false);
      }
      expect(typeof p.actual_points).toBe('number');
    });
  });
});
