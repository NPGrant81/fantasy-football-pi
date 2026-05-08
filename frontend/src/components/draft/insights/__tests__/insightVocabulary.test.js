import { describe, it, expect } from 'vitest';
import {
  confidenceTier,
  confidenceFromRisk,
  confidenceBand,
  explainRecommendation,
  riskLabel,
  tierTone,
  severityClasses,
  strategyBreakSeverity,
  INSIGHT_SEVERITY,
  UX_PRIORITY,
  POSITION_CAPS,
} from '../insightVocabulary';

describe('insightVocabulary', () => {
  describe('confidenceTier', () => {
    it('returns high for risk < 30', () => {
      expect(confidenceTier(0)).toBe('high');
      expect(confidenceTier(29)).toBe('high');
    });

    it('returns moderate for risk 30-54', () => {
      expect(confidenceTier(30)).toBe('moderate');
      expect(confidenceTier(42)).toBe('moderate');
      expect(confidenceTier(54)).toBe('moderate');
    });

    it('returns low for risk 55-79', () => {
      expect(confidenceTier(55)).toBe('low');
      expect(confidenceTier(70)).toBe('low');
      expect(confidenceTier(79)).toBe('low');
    });

    it('returns degraded for risk >= 80', () => {
      expect(confidenceTier(80)).toBe('degraded');
      expect(confidenceTier(95)).toBe('degraded');
    });

    it('handles null/undefined gracefully', () => {
      expect(confidenceTier(null)).toBe('degraded');
      expect(confidenceTier(undefined)).toBe('degraded');
    });
  });

  describe('confidenceFromRisk', () => {
    it('returns high confidence (95) for low risk (5)', () => {
      expect(confidenceFromRisk(5)).toBe(95);
    });

    it('returns low confidence (20) for high risk (80)', () => {
      expect(confidenceFromRisk(80)).toBe(20);
    });

    it('clamps to [5, 95] range', () => {
      expect(confidenceFromRisk(-10)).toBe(95); // 100 - (-10) = 110, clamped to 95
      expect(confidenceFromRisk(120)).toBe(5); // 100 - 120 = -20, clamped to 5
    });
  });

  describe('confidenceBand', () => {
    it('creates symmetric band around recommended bid', () => {
      const band = confidenceBand(100, 30);
      expect(band.low).toBeLessThan(100);
      expect(band.high).toBeGreaterThan(100);
    });

    it('widens band for higher risk scores', () => {
      const lowRiskBand = confidenceBand(100, 20);
      const highRiskBand = confidenceBand(100, 70);
      expect(highRiskBand.high - highRiskBand.low).toBeGreaterThan(
        lowRiskBand.high - lowRiskBand.low
      );
    });

    it('enforces minimum bid of $1', () => {
      const band = confidenceBand(1, 100);
      expect(band.low).toBeGreaterThanOrEqual(1);
    });
  });

  describe('riskLabel', () => {
    it('returns Low for risk < 45', () => {
      expect(riskLabel(0)).toBe('Low');
      expect(riskLabel(44)).toBe('Low');
    });

    it('returns Moderate for risk 45-69', () => {
      expect(riskLabel(45)).toBe('Moderate');
      expect(riskLabel(60)).toBe('Moderate');
    });

    it('returns High for risk >= 70', () => {
      expect(riskLabel(70)).toBe('High');
      expect(riskLabel(100)).toBe('High');
    });
  });

  describe('tierTone', () => {
    it('returns color classes for each tier', () => {
      expect(tierTone('S')).toContain('emerald');
      expect(tierTone('A')).toContain('cyan');
      expect(tierTone('B')).toContain('blue');
      expect(tierTone('C')).toContain('amber');
      expect(tierTone('D')).toContain('rose');
    });

    it('defaults to rose for unknown tier', () => {
      expect(tierTone('unknown')).toContain('rose');
    });
  });

  describe('severityClasses', () => {
    it('returns rose classes for CRITICAL', () => {
      const classes = severityClasses(INSIGHT_SEVERITY.CRITICAL);
      expect(classes).toContain('rose');
    });

    it('returns amber classes for WARNING', () => {
      const classes = severityClasses(INSIGHT_SEVERITY.WARNING);
      expect(classes).toContain('amber');
    });

    it('returns cyan classes for INFO', () => {
      const classes = severityClasses(INSIGHT_SEVERITY.INFO);
      expect(classes).toContain('cyan');
    });

    it('returns slate classes for NEUTRAL', () => {
      const classes = severityClasses(INSIGHT_SEVERITY.NEUTRAL);
      expect(classes).toContain('slate');
    });
  });

  describe('strategyBreakSeverity', () => {
    it('returns CRITICAL when exceeds position cap', () => {
      const result = strategyBreakSeverity({ exceedsPosCap: true });
      expect(result).toBe(INSIGHT_SEVERITY.CRITICAL);
    });

    it('returns WARNING when behind position average', () => {
      const result = strategyBreakSeverity({
        mostBehindPosition: { delta: -2 },
      });
      expect(result).toBe(INSIGHT_SEVERITY.WARNING);
    });

    it('returns null when no alert condition', () => {
      const result = strategyBreakSeverity({
        exceedsPosCap: false,
        mostBehindPosition: { delta: 0.5 },
      });
      expect(result).toBeNull();
    });

    it('prioritizes CRITICAL over WARNING', () => {
      const result = strategyBreakSeverity({
        exceedsPosCap: true,
        mostBehindPosition: { delta: -2 },
      });
      expect(result).toBe(INSIGHT_SEVERITY.CRITICAL);
    });
  });

  describe('explainRecommendation', () => {
    it('returns null for missing recommendation', () => {
      expect(explainRecommendation(null)).toBeNull();
      expect(explainRecommendation(undefined)).toBeNull();
    });

    it('returns degraded snippet for very high risk', () => {
      const rec = {
        player_name: 'Test Player',
        risk_score: 85,
        recommended_bid: 50,
        position: 'WR',
      };
      const snippet = explainRecommendation(rec);
      expect(snippet).toContain('confidence is too low');
    });

    it('returns low-confidence snippet for high risk', () => {
      const rec = {
        player_name: 'Test Player',
        risk_score: 70,
        recommended_bid: 50,
        position: 'WR',
      };
      const snippet = explainRecommendation(rec);
      expect(snippet).toContain('high volatility');
      expect(snippet).toContain('widen');
    });

    it('returns moderate snippet for medium risk', () => {
      const rec = {
        player_name: 'Test Player',
        risk_score: 45,
        recommended_bid: 50,
        position: 'QB',
      };
      const snippet = explainRecommendation(rec);
      expect(snippet).toContain('solid');
      expect(snippet).toContain('moderate risk');
    });

    it('returns high-confidence snippet for low risk', () => {
      const rec = {
        player_name: 'Test Player',
        risk_score: 20,
        recommended_bid: 50,
        position: 'RB',
      };
      const snippet = explainRecommendation(rec);
      expect(snippet).toContain('strong');
      expect(snippet).toContain('high model confidence');
    });

    it('includes budget context when provided', () => {
      const rec = {
        player_name: 'Test',
        risk_score: 30,
        recommended_bid: 50,
        position: 'WR',
      };
      const snippet = explainRecommendation(rec, { budget: 100 });
      expect(snippet).toContain('50%');
      expect(snippet).toContain('remaining budget');
    });

    it('uses player name in snippet', () => {
      const rec = {
        player_name: 'Patrick Mahomes',
        risk_score: 25,
        recommended_bid: 35,
        position: 'QB',
      };
      const snippet = explainRecommendation(rec);
      expect(snippet).toContain('Patrick Mahomes');
    });
  });

  describe('constants', () => {
    it('defines UX_PRIORITY with MUST_KNOW entries', () => {
      expect(UX_PRIORITY.RECOMMENDED_BID).toBe('MUST_KNOW');
      expect(UX_PRIORITY.CONFIDENCE_BAND).toBe('MUST_KNOW');
      expect(UX_PRIORITY.BARGAIN_FLAG).toBe('MUST_KNOW');
    });

    it('defines INSIGHT_SEVERITY levels', () => {
      expect(Object.keys(INSIGHT_SEVERITY)).toContain('CRITICAL');
      expect(Object.keys(INSIGHT_SEVERITY)).toContain('WARNING');
      expect(Object.keys(INSIGHT_SEVERITY)).toContain('INFO');
      expect(Object.keys(INSIGHT_SEVERITY)).toContain('NEUTRAL');
    });

    it('defines POSITION_CAPS for all positions', () => {
      expect(POSITION_CAPS.QB).toBe(2);
      expect(POSITION_CAPS.RB).toBe(5);
      expect(POSITION_CAPS.WR).toBe(5);
      expect(POSITION_CAPS.TE).toBe(2);
      expect(POSITION_CAPS.DEF).toBe(1);
      expect(POSITION_CAPS.K).toBe(1);
    });
  });
});
