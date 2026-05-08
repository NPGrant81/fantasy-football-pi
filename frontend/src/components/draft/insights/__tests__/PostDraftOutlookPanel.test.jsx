import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PostDraftOutlookPanel from '../PostDraftOutlookPanel';

describe('PostDraftOutlookPanel', () => {
  it('renders empty state when outlook is unavailable', () => {
    render(<PostDraftOutlookPanel outlook={null} ownerLabel="Alpha" />);
    expect(screen.getByText(/Post-draft outlook appears/i)).toBeInTheDocument();
  });

  it('renders primary metrics and lists when outlook is provided', () => {
    render(
      <PostDraftOutlookPanel
        ownerLabel="Alpha"
        outlook={{
          rosterStrengthScore: 173.4,
          projectedStarterValue: 96,
          budgetDeltaVsLeague: -12,
          simulationDelta: 8.5,
          strongestPositions: [{ position: 'WR', count: 4, cap: 5 }],
          thinnestPositions: [{ position: 'TE', count: 1, cap: 2 }],
          highRiskPlayers: [{ player_id: 101, name: 'Risky Player', position: 'RB', risk: 72 }],
          positionCounts: [
            { position: 'QB', count: 1, cap: 2 },
            { position: 'RB', count: 3, cap: 5 },
          ],
        }}
      />
    );

    expect(screen.getByText(/Post-Draft Outlook \(Alpha\)/i)).toBeInTheDocument();
    expect(screen.getByText('173.4')).toBeInTheDocument();
    expect(screen.getByText('$96')).toBeInTheDocument();
    expect(screen.getByText('-12')).toBeInTheDocument();
    expect(screen.getByText('+8.5 pts')).toBeInTheDocument();

    expect(screen.getByText('WR: 4/5')).toBeInTheDocument();
    expect(screen.getByText('TE: 1/2')).toBeInTheDocument();
    expect(screen.getByText(/Risky Player \(RB\) · risk 72/i)).toBeInTheDocument();
    expect(screen.getByText('QB 1/2')).toBeInTheDocument();
    expect(screen.getByText('RB 3/5')).toBeInTheDocument();
  });

  it('shows em dash when simulation delta is unavailable', () => {
    render(
      <PostDraftOutlookPanel
        ownerLabel="Alpha"
        outlook={{
          rosterStrengthScore: 10,
          projectedStarterValue: 5,
          budgetDeltaVsLeague: 0,
          simulationDelta: null,
          strongestPositions: [],
          thinnestPositions: [],
          highRiskPlayers: [],
          positionCounts: [{ position: 'QB', count: 1, cap: 2 }],
        }}
      />
    );

    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.getByText(/No clear strengths yet/i)).toBeInTheDocument();
    expect(screen.getByText(/Depth looks balanced/i)).toBeInTheDocument();
    expect(screen.getByText(/No high-risk flags/i)).toBeInTheDocument();
  });
});
