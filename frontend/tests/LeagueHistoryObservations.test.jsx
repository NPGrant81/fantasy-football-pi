import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import apiClient from '../src/api/client';
import LeagueHistory from '../src/pages/history/LeagueHistory';

vi.mock('../src/api/client', () => ({ default: { get: vi.fn() } }));
vi.mock('../src/context/LeagueContext', () => ({ useActiveLeague: () => 60 }));
vi.mock('../src/components/layout/PageTemplate', () => ({
  default: ({ children }) => <main>{children}</main>,
}));
vi.mock('react-chartjs-2', () => ({ Line: () => null, Bar: () => null }));

describe('Historical auction observations', () => {
  afterEach(() => {
    document.documentElement.classList.remove('dark');
  });

  beforeEach(() => {
    vi.clearAllMocks();
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/owners')) return Promise.resolve({ data: [] });
      if (url.startsWith('/draft/seasons')) return Promise.resolve({ data: [2024] });
      if (url.startsWith('/draft/history/by-year')) {
        return Promise.resolve({
          data: [{
            id: 'observation-1', owner_id: 91, player_id: 11,
            owner_label: 'MFL franchise 0002', player_name: 'Reviewed Player',
            amount: '999999999999.999999', timestamp: null,
            event_grain: 'historical_auction_observation',
          }],
        });
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
  });

  it.each(['light', 'dark'])('preserves labels, observation grain and exact bids in %s mode', async (theme) => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    render(
      <MemoryRouter>
        <LeagueHistory sectionKey="historical-analytics" />
      </MemoryRouter>
    );
    expect(await screen.findByText('Reviewed Player')).toBeInTheDocument();
    expect(screen.getByText('MFL franchise 0002')).toBeInTheDocument();
    expect(screen.getByText('$999999999999.999999')).toBeInTheDocument();
    expect(screen.getByText(/order and current ownership not established/)).toBeInTheDocument();
    expect(screen.queryByText('Owner 91')).not.toBeInTheDocument();
  });
});
