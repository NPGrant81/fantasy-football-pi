/* ignore-breakpoints */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PlayerInsightCard from '../PlayerInsightCard';

describe('PlayerInsightCard', () => {
  const mockRecommendation = {
    player_name: 'Travis Kelce',
    recommended_bid: 42,
    risk_score: 35,
    value_score: 47.8,
    tier: 'A',
    predicted_value: 50,
    position: 'TE',
    flags: [],
  };

  const mockScarcityByPosition = [
    { position: 'TE', scarcity: 75 },
    { position: 'WR', scarcity: 45 },
    { position: 'RB', scarcity: 60 },
  ];

  it('renders empty state when no recommendation', () => {
    render(<PlayerInsightCard recommendation={null} bidAmount={0} />);
    expect(screen.getByText(/Select a draftable player/i)).toBeInTheDocument();
  });

  it('renders player name when recommendation exists', () => {
    render(
      <PlayerInsightCard
        recommendation={mockRecommendation}
        bidAmount={0}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    expect(screen.getByText('Travis Kelce')).toBeInTheDocument();
  });

  it('shows explainability snippet for moderate risk', () => {
    render(
      <PlayerInsightCard
        recommendation={mockRecommendation}
        bidAmount={0}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    // Risk score 35 is moderate (30-54), should show "solid value" snippet
    const snippet = screen.getByText(/solid.*value/i);
    expect(snippet).toBeInTheDocument();
  });

  it('shows recommended bid prominently', () => {
    render(
      <PlayerInsightCard
        recommendation={mockRecommendation}
        bidAmount={0}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    expect(screen.getByText(/\$42\.00/)).toBeInTheDocument();
  });

  it('shows confidence percentage from risk score', () => {
    render(
      <PlayerInsightCard
        recommendation={mockRecommendation}
        bidAmount={0}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    // Risk 35 -> confidence = 65
    expect(screen.getByText(/65%/)).toBeInTheDocument();
  });

  it('shows value score and tier', () => {
    render(
      <PlayerInsightCard
        recommendation={mockRecommendation}
        bidAmount={0}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    expect(screen.getByText('47.80')).toBeInTheDocument();
    expect(screen.getByText('A')).toBeInTheDocument();
  });

  it('shows low-confidence warning for high-risk recommendation', () => {
    const highRiskRec = { ...mockRecommendation, risk_score: 75 };
    render(
      <PlayerInsightCard
        recommendation={highRiskRec}
        bidAmount={0}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument();
  });

  it('shows bargain flag when bid is below predicted value', () => {
    render(
      <PlayerInsightCard
        recommendation={mockRecommendation}
        bidAmount={40}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    expect(screen.getByText(/Bargain opportunity/i)).toBeInTheDocument();
  });

  it('shows overpriced flag when bid is above recommended', () => {
    render(
      <PlayerInsightCard
        recommendation={mockRecommendation}
        bidAmount={50}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    expect(screen.getByText(/Overpriced/i)).toBeInTheDocument();
  });

  it('calculates confidence tier for color coding', () => {
    const { rerender } = render(
      <PlayerInsightCard
        recommendation={{ ...mockRecommendation, risk_score: 25 }}
        bidAmount={0}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    // Risk 25 = high tier, should show high-confidence framing
    expect(screen.queryByText(/confidence is too low/i)).not.toBeInTheDocument();

    rerender(
      <PlayerInsightCard
        recommendation={{ ...mockRecommendation, risk_score: 50 }}
        bidAmount={0}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    // Risk 50 = moderate tier
    expect(screen.queryByText(/confidence is too low/i)).not.toBeInTheDocument();

    rerender(
      <PlayerInsightCard
        recommendation={{ ...mockRecommendation, risk_score: 75 }}
        bidAmount={0}
        scarcityByPosition={mockScarcityByPosition}
      />
    );
    // Risk 75 = low tier, should show caution
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument();
  });
});
