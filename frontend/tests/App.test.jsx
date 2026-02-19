import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

// Mock child components to keep App render surface-level and deterministic
vi.mock('../src/components/Layout', () => ({
  default: ({ children }) => <div data-testid="layout">{children}</div>,
}));
vi.mock('../src/pages/Dashboard', () => ({
  default: () => <div>Dashboard</div>,
}));
vi.mock('../src/pages/DraftBoard', () => ({ default: () => <div>Draft</div> }));
vi.mock('../src/pages/team-owner/MyTeam', () => ({
  default: () => <div>MyTeam</div>,
}));
vi.mock('../src/pages/matchups/Matchups', () => ({
  default: () => <div>Matchups</div>,
}));
vi.mock('../src/pages/matchups/GameCenter', () => ({
  default: () => <div>GameCenter</div>,
}));
vi.mock('../src/pages/commissioner/CommissionerDashboard', () => ({
  default: () => <div>Commissioner</div>,
}));
vi.mock('../src/pages/WaiverWire', () => ({
  default: () => <div>Waivers</div>,
}));
vi.mock('../src/pages/admin/SiteAdmin', () => ({
  default: () => <div>Admin</div>,
}));
vi.mock('../src/pages/BugReport', () => ({ default: () => <div>BugReport</div> }));

// Mock apiClient used by App
vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import App from '../src/App';
import apiClient from '../src/api/client';

describe('App (basic)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders login screen when no token present', () => {
    render(<App />);
    expect(screen.getByText(/FantasyFootball-PI Login/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Enter username/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Enter password/i)).toBeInTheDocument();
    // Test for new League ID input (from recent changes)
    expect(screen.getByPlaceholderText(/Enter league ID/i)).toBeInTheDocument();
    // Verify default league is set to "The Big Show" (ID 1)
    const leagueInput = screen.getByDisplayValue('1');
    expect(leagueInput).toBeInTheDocument();
  });

  test('uses token to fetch /auth/me and shows app when valid', async () => {
    localStorage.setItem('fantasyToken', 'fake-token');
    localStorage.setItem('fantasyLeagueId', '1');
    apiClient.get.mockResolvedValue({
      data: { user_id: 7, username: 'alice' },
    });

    render(<App />);

    // Wait for effect to run and children to render inside Layout
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/auth/me'));
    expect(localStorage.getItem('fantasyToken')).toBe('fake-token');
    expect(screen.getByTestId('layout')).toBeInTheDocument();
  });

  test('login form submission saves league ID from input (not from server)', async () => {
    // Setup
    apiClient.post.mockResolvedValue({
      data: { access_token: 'new-token', owner_id: 42 },
      // Note: No league_id in response - App must use form input instead
    });
    apiClient.get.mockResolvedValue({
      data: { user_id: 42, username: 'testuser' },
    });

    render(<App />);
    const user = userEvent.setup();

    // Fill in the form with custom league ID
    const usernameInput = screen.getByPlaceholderText(/Enter username/i);
    const passwordInput = screen.getByPlaceholderText(/Enter password/i);
    const leagueIdInput = screen.getByPlaceholderText(/Enter league ID/i);

    await user.type(usernameInput, 'testuser');
    await user.type(passwordInput, 'password');
    await user.clear(leagueIdInput);
    await user.type(leagueIdInput, '5'); // Change from default (1) to 5

    // Submit form
    const submitButton = screen.getByRole('button', { name: /ENTER/i });
    await user.click(submitButton);

    // Verify token endpoint was called
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        '/auth/token',
        expect.any(Object),
        expect.any(Object)
      )
    );

    // Verify league ID from form input is saved (not from server response)
    await waitFor(() => {
      expect(localStorage.getItem('fantasyLeagueId')).toBe('5');
    });
  });
});