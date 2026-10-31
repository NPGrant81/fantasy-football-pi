import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import apiClient from '../src/api/client';
import { LeagueContext } from '../src/context/LeagueContext';
import ManageWaiverRules from '../src/pages/commissioner/ManageWaiverRules';

function Page({ leagueId = '1' }) {
  return (
    <MemoryRouter>
      <LeagueContext.Provider value={{ activeLeagueId: leagueId }}>
        <ManageWaiverRules />
      </LeagueContext.Provider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
  apiClient.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith('/settings') ? {} : [] }));
});

it('uses the supported league-scoped API and renders populated history', async () => {
  apiClient.get.mockImplementation((url) => Promise.resolve({
    data: url === '/waivers/claims'
      ? [{ id: 1, username: 'Alice', player_name: 'Runner', bid_amount: 7, status: 'WON' }]
      : url.endsWith('/settings') ? {} : [],
  }));
  render(<Page />);
  expect(await screen.findByText('Runner')).toBeInTheDocument();
  expect(apiClient.get).toHaveBeenCalledWith('/waivers/claims', expect.objectContaining({ params: { league_id: '1' } }));
});

it('distinguishes a genuinely empty history from failure', async () => {
  render(<Page />);
  expect(await screen.findByText('No claims recorded yet.')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

it.each([403, 500])('surfaces HTTP %s and permits a real query retry', async (status) => {
  let failing = true;
  apiClient.get.mockImplementation((url) => {
    if (url === '/waivers/claims' && failing) {
      return Promise.reject({ response: { status } });
    }
    return Promise.resolve({ data: url.endsWith('/settings') ? {} : [] });
  });
  render(<Page />);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    status === 403 ? 'permission' : 'Failed to load waiver history'
  );
  expect(screen.queryByText('No claims recorded yet.')).not.toBeInTheDocument();
  failing = false;
  await userEvent.click(screen.getByRole('button', { name: 'Retry waiver history' }));
  expect(await screen.findByText('No claims recorded yet.')).toBeInTheDocument();
});

it('does not display stale results after switching leagues', async () => {
  let resolveFirst;
  apiClient.get.mockImplementation((url, options) => {
    if (url !== '/waivers/claims') return Promise.resolve({ data: {} });
    if (options.params.league_id === '1') {
      return new Promise((resolve) => { resolveFirst = resolve; });
    }
    return Promise.resolve({ data: [{ id: 2, player_name: 'New league player', status: 'WON' }] });
  });
  const { rerender } = render(<Page />);
  await waitFor(() => expect(resolveFirst).toBeDefined());
  rerender(<Page leagueId="2" />);
  expect(await screen.findByText('New league player')).toBeInTheDocument();
  await act(async () => resolveFirst({ data: [{ id: 1, player_name: 'Old league player' }] }));
  expect(screen.queryByText('Old league player')).not.toBeInTheDocument();
});
