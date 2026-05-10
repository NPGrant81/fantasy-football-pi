import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import InSeasonAdvisorPanel from '../InSeasonAdvisorPanel';

vi.mock('@api/analyticsApi', () => ({
  askInSeasonAdvisor: vi.fn(),
}));

import { askInSeasonAdvisor } from '@api/analyticsApi';

describe('InSeasonAdvisorPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows disabled placeholder when missing league/owner context', () => {
    render(
      <InSeasonAdvisorPanel
        leagueId={null}
        ownerId={null}
        season={2026}
        username="tester"
        inSeasonContext={null}
      />
    );

    expect(screen.getByPlaceholderText(/No league context available/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send query/i })).toBeDisabled();
  });

  it('sends query and renders advisor response', async () => {
    askInSeasonAdvisor.mockResolvedValue({
      response: 'Start your highest-projected WR in flex this week.',
    });

    render(
      <InSeasonAdvisorPanel
        leagueId={10}
        ownerId={2}
        season={2026}
        username="tester"
        inSeasonContext={{ roster_needs: [], waiver_targets: [] }}
      />
    );

    const input = screen.getByLabelText(/Advisor query input/i);
    fireEvent.change(input, { target: { value: 'Who should I start?' } });
    fireEvent.click(screen.getByRole('button', { name: /send query/i }));

    await waitFor(() => {
      expect(askInSeasonAdvisor).toHaveBeenCalled();
      expect(screen.getByText(/Start your highest-projected WR/i)).toBeInTheDocument();
    });
  });

  it('supports quick prompt buttons', async () => {
    askInSeasonAdvisor.mockResolvedValue({
      response: 'Top waiver target this week is RB depth.',
    });

    render(
      <InSeasonAdvisorPanel
        leagueId={10}
        ownerId={2}
        season={2026}
        username="tester"
        inSeasonContext={{ roster_needs: ['RB'], waiver_targets: [] }}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /who should i target on waivers\?/i }));

    await waitFor(() => {
      expect(askInSeasonAdvisor).toHaveBeenCalled();
      expect(screen.getByText(/Top waiver target/i)).toBeInTheDocument();
    });
  });
});
