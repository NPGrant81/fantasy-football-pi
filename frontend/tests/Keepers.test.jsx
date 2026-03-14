import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('react-router-dom', () => ({
  Link: ({ to, children, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

import Keepers from '../src/pages/Keepers';
import apiClient from '../src/api/client';

describe('Keepers page', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders loading state', () => {
    apiClient.get.mockImplementation(() => new Promise(() => {}));
    render(<Keepers />);
    expect(screen.getByText(/Loading keepers/i)).toBeInTheDocument();
  });

  test('fetches keeper data with owner context and available players', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { user_id: 1, username: 'alice', league_id: 1 },
        });
      }
      if (url === '/keepers/') {
        return Promise.resolve({
          data: {
            owner_id: 1,
            owner_name: 'Alice',
            selections: [],
            recommended: [
              { player_id: 10, surplus: 30, keep_cost: 5, projected_value: 35 },
            ],
            available_players: [
              {
                player_id: 10,
                name: 'Player Alice',
                position: 'RB',
                nfl_team: 'KC',
                draft_price: 20,
                is_selected: false,
                is_eligible: true,
                reason_ineligible: null,
                years_kept_count: 0,
              },
            ],
            selected_count: 0,
            max_allowed: 3,
            estimated_budget: 200,
            effective_budget: 200,
          },
        });
      }
      return Promise.reject(new Error('unknown'));
    });

    render(<Keepers />);
    await waitFor(() =>
      expect(screen.getByText(/Manage Keepers - Alice/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/Effective Budget: \$200/i)).toBeInTheDocument();
    // Check for player in the roster section (not recommended)
    expect(screen.getByText(/Your Roster - Available to Keep/i)).toBeInTheDocument();
    expect(screen.getByText(/💡 Recommended Keepers/i)).toBeInTheDocument();
  });

  test('ineligible players show reason and are disabled', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { user_id: 1, username: 'alice', league_id: 1 },
        });
      }
      if (url === '/keepers/') {
        return Promise.resolve({
          data: {
            owner_id: 1,
            owner_name: 'Bob',
            selections: [],
            recommended: [],
            available_players: [
              {
                player_id: 10,
                name: 'Player Alice',
                position: 'WR',
                nfl_team: 'NYG',
                draft_price: 5,
                is_selected: false,
                is_eligible: false,
                reason_ineligible: 'Already designated as keeper for 2 year(s); max allowed is 1',
                years_kept_count: 2,
              },
            ],
            selected_count: 0,
            max_allowed: 3,
            estimated_budget: 100,
            effective_budget: 100,
          },
        });
      }
      return Promise.reject(new Error('unknown'));
    });

    render(<Keepers />);
    await waitFor(() => screen.getByText('Player Alice'));
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeDisabled();
    expect(screen.getByText(/Already designated as keeper/i)).toBeInTheDocument();
  });

  test('toggle player and submit', async () => {
    let callCount = 0;
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { user_id: 1, username: 'alice', league_id: 1 },
        });
      }
      if (url === '/keepers/') {
        callCount++;
        return Promise.resolve({
          data: {
            owner_id: 1,
            owner_name: 'Charlie',
            selections: callCount === 1 ? [] : [{ player_id: 10 }],
            recommended: [],
            available_players: [
              {
                player_id: 10,
                name: 'Player Alice',
                position: 'QB',
                nfl_team: 'SF',
                draft_price: 20,
                is_selected: callCount === 1 ? false : true,
                is_eligible: true,
                reason_ineligible: null,
                years_kept_count: 0,
              },
            ],
            selected_count: callCount === 1 ? 0 : 1,
            max_allowed: 1,
            estimated_budget: 100,
            effective_budget: 100,
          },
        });
      }
      return Promise.reject(new Error('unknown'));
    });

    apiClient.post.mockResolvedValue({ data: {} });

    render(<Keepers />);
    await waitFor(() => {
      expect(screen.getByText(/Your Roster - Available to Keep/i)).toBeInTheDocument();
    });

    // Find the checkbox by role
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeInTheDocument();
    fireEvent.click(checkbox);

    // Find submit button
    const submitBtn = screen.getByRole('button', { name: /Save Selections/i });
    expect(submitBtn).toBeInTheDocument();
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/keepers/',
        expect.objectContaining({
          players: expect.any(Array),
        })
      );
    });

    await waitFor(
      () => {
        const allText = document.documentElement.textContent;
        expect(allText).toMatch(/1 of 1 chosen/i);
      },
      { timeout: 2000 }
    );
  });

  test('loads roster candidates from auth session when localStorage user_id is missing', async () => {
    localStorage.removeItem('user_id');

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { user_id: 7, username: 'alice', league_id: 1 },
        });
      }
      if (url === '/keepers/') {
        return Promise.resolve({
          data: {
            selections: [],
            recommended: [],
            selected_count: 0,
            max_allowed: 3,
            estimated_budget: 150,
            effective_budget: 150,
          },
        });
      }
      if (url.startsWith('/team/7?week=')) {
        return Promise.resolve({
          data: {
            players: [
              {
                player_id: 22,
                name: 'Keeper Candidate',
                draft_price: 12,
                projected_value: 30,
              },
            ],
          },
        });
      }
      return Promise.reject(new Error(`unknown ${url}`));
    });

    render(<Keepers />);

    await waitFor(() => {
      expect(screen.getByText(/Keeper Candidate/)).toBeInTheDocument();
    });

    expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    expect(apiClient.get).toHaveBeenCalledWith('/keepers/');
    expect(apiClient.get).toHaveBeenCalledWith('/team/7?week=1');
  });
});
