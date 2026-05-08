/* ignore-breakpoints */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import OwnerStrategyPanel from '../OwnerStrategyPanel';

const baseInsights = {
  ownerStats: { budget: 40 },
  leagueAvgBudget: 55,
  aggressivenessIndex: 1.0,
  strategyAlignmentScore: 78,
  mostBehindPosition: { position: 'WR', delta: -2 },
  exceedsPosCap: false,
  selectedPos: 'WR',
  posMaxSpend: 20,
};

describe('OwnerStrategyPanel perspective wording', () => {
  it('uses third-person wording when viewing another owner', () => {
    render(
      <OwnerStrategyPanel
        insightOwnerId={2}
        insightOwnerLabel="Owner Alpha"
        isCurrentUserOwner={false}
        ownerStrategyInsights={baseInsights}
        recommendation={{ recommended_bid: 10 }}
      />
    );

    expect(screen.getByText(/Owner Alpha is behind league average at WR\./i)).toBeInTheDocument();
    expect(screen.getByText(/If Owner Alpha wins at \$10\.00, Owner Alpha keeps \$30\.00 left\./i)).toBeInTheDocument();
  });

  it('keeps second-person wording for the active user owner view', () => {
    render(
      <OwnerStrategyPanel
        insightOwnerId={1}
        insightOwnerLabel="Owner You"
        isCurrentUserOwner={true}
        ownerStrategyInsights={baseInsights}
        recommendation={{ recommended_bid: 10 }}
      />
    );

    expect(screen.getByText(/You are behind league average at WR\./i)).toBeInTheDocument();
    expect(screen.getByText(/If you win at \$10\.00, you keep \$30\.00 left\./i)).toBeInTheDocument();
  });
});
