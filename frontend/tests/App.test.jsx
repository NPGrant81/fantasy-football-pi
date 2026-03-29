import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

// Mock child components to keep App render surface-level and deterministic
let capturedLayoutProps = {};
vi.mock('../src/components/Layout', () => ({
  default: (props) => {
    capturedLayoutProps = props;
    return <div data-testid="layout">{props.children}</div>;
  },
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
vi.mock('../src/pages/BugReport', () => ({
  default: () => <div>BugReport</div>,
}));
// add playoff bracket mock for routing test
vi.mock('../src/pages/playoffs/PlayoffBracket', () => ({
  default: () => <div>PlayoffBracket</div>,
}));

// Mock apiClient used by App
vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import App from '../src/App';
import apiClient from '../src/api/client';
import { emitVisitEvent } from '../src/services/visitLogger';

vi.mock('../src/services/visitLogger', () => ({
  emitVisitEvent: vi.fn(),
}));

describe('App (basic)', () => {
  beforeEach(() => {
    capturedLayoutProps = {};
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders login screen when no token present', () => {
    render(<App />);
    expect(screen.getByText(/PPL Insight Hub Login/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Enter username/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Enter password/i)).toBeInTheDocument();
    // Test for new League ID input (from recent changes)
    expect(screen.getByPlaceholderText(/Enter league ID/i)).toBeInTheDocument();
    // Verify default league is set to "The Big Show" (ID 1)
    const leagueInput = screen.getByDisplayValue('1');
    expect(leagueInput).toBeInTheDocument();
    expect(emitVisitEvent).toHaveBeenCalledWith('/', null);
  });

  test('uses token to fetch /auth/me and shows app when valid', async () => {
    localStorage.setItem('fantasyToken', 'fake-token');
    localStorage.setItem('fantasyLeagueId', '1');
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me')
        return Promise.resolve({ data: { user_id: 7, username: 'alice', league_id: 1 } });
      if (url === '/leagues/1/settings')
        return Promise.resolve({
          data: { waiver_deadline: 'Thu 4pm', trade_deadline: 'Sun 8pm' },
        });
      return Promise.resolve({ data: {} });
    });

    render(<App />);

    // Wait for primary effect
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/auth/me'));
    expect(localStorage.getItem('fantasyToken')).toBe('fake-token');
    expect(screen.getByTestId('layout')).toBeInTheDocument();

    // since league settings were fetched, Layout.alert should include our deadlines
    await waitFor(() => {
      expect(capturedLayoutProps.alert).toMatch(/Waiver: Thu 4pm/);
      expect(capturedLayoutProps.alert).toMatch(/Trade: Sun 8pm/);
    });
  });

  test('login without server league_id does not persist arbitrary league from input', async () => {
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

    // Verify we do not force a league from client-side input when server omitted league_id.
    await waitFor(() => {
      expect(localStorage.getItem('fantasyLeagueId')).toBeNull();
      // Verify fantasyToken is set so auth persists across refresh
      expect(localStorage.getItem('fantasyToken')).toBe('cookie-session');
    });

    // With no active league, app should route to league selector flow.
    expect(screen.getByText(/Select your league to enter/i)).toBeInTheDocument();
  });

  test('logout clears fantasyToken so auth check is not re-triggered', async () => {
    localStorage.setItem('fantasyToken', 'cookie-session');
    localStorage.setItem('fantasyLeagueId', '1');
    localStorage.setItem('user_id', '7');
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me')
        return Promise.resolve({ data: { user_id: 7, username: 'alice', league_id: 1 } });
      return Promise.resolve({ data: {} });
    });
    apiClient.post.mockResolvedValue({});

    render(<App />);
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/auth/me'));
    expect(screen.getByTestId('layout')).toBeInTheDocument();

    // Trigger logout via the captured Layout prop
    await act(async () => {
      await capturedLayoutProps.onLogout();
    });

    await waitFor(() => {
      expect(localStorage.getItem('fantasyToken')).toBeNull();
      expect(localStorage.getItem('user_id')).toBeNull();
    });
    expect(screen.getByText(/PPL Insight Hub Login/i)).toBeInTheDocument();
  });

  test('logout deduplicates in-flight /auth/logout requests', async () => {
    localStorage.setItem('fantasyToken', 'cookie-session');
    localStorage.setItem('fantasyLeagueId', '1');
    localStorage.setItem('user_id', '7');

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({ data: { user_id: 7, username: 'alice', league_id: 1 } });
      }
      return Promise.resolve({ data: {} });
    });

    let resolveLogout;
    const logoutPromise = new Promise((resolve) => {
      resolveLogout = resolve;
    });

    apiClient.post.mockImplementation((url) => {
      if (url === '/auth/logout') {
        return logoutPromise;
      }
      return Promise.resolve({ data: {} });
    });

    render(<App />);
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/auth/me'));

    await act(async () => {
      capturedLayoutProps.onLogout();
      capturedLayoutProps.onLogout();
    });

    const logoutCalls = apiClient.post.mock.calls.filter(([url]) => url === '/auth/logout');
    expect(logoutCalls).toHaveLength(1);

    await act(async () => {
      resolveLogout({});
      await logoutPromise;
    });
  });

  test('login aborts pending logout before requesting /auth/token', async () => {
    localStorage.setItem('fantasyToken', 'cookie-session');
    localStorage.setItem('fantasyLeagueId', '1');
    localStorage.setItem('user_id', '7');

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({ data: { user_id: 7, username: 'alice', league_id: 1 } });
      }
      if (url === '/leagues/1/settings') {
        return Promise.resolve({ data: {} });
      }
      return Promise.resolve({ data: {} });
    });

    let capturedLogoutSignal = null;
    apiClient.post.mockImplementation((url, body, config) => {
      if (url === '/auth/logout') {
        capturedLogoutSignal = config?.signal || null;
        return new Promise((resolve, reject) => {
          capturedLogoutSignal?.addEventListener(
            'abort',
            () => {
              reject(new Error('aborted'));
              resolve({});
            },
            { once: true }
          );
        });
      }

      if (url === '/auth/token') {
        return Promise.resolve({
          data: { owner_id: 7, league_id: 1, is_commissioner: false, is_superuser: false },
        });
      }

      return Promise.resolve({ data: {} });
    });

    render(<App />);
    const user = userEvent.setup();

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/auth/me'));

    await act(async () => {
      capturedLayoutProps.onLogout();
    });

    await user.type(screen.getByPlaceholderText(/Enter username/i), 'alice');
    await user.type(screen.getByPlaceholderText(/Enter password/i), 'pw');
    await user.click(screen.getByRole('button', { name: /ENTER/i }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        '/auth/token',
        expect.any(Object),
        expect.any(Object)
      )
    );

    expect(capturedLogoutSignal).not.toBeNull();
    expect(capturedLogoutSignal.aborted).toBe(true);
  });

  test('token-present users without a mapped league can select one and enter the app', async () => {
    localStorage.setItem('fantasyToken', 'cookie-session');
    localStorage.setItem('user_id', '7');

    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { user_id: 7, username: 'alice', league_id: null, is_commissioner: false },
        });
      }
      if (url === '/leagues/') {
        return Promise.resolve({ data: [{ id: 5, name: 'Dynasty Five' }] });
      }
      if (url === '/leagues/5/settings') {
        return Promise.resolve({ data: {} });
      }
      return Promise.resolve({ data: {} });
    });

    apiClient.post.mockImplementation((url, body, config) => {
      if (url === '/leagues/join') {
        expect(config).toEqual({ params: { league_id: 5 } });
        return Promise.resolve({ data: { message: 'Welcome to Dynasty Five!' } });
      }
      return Promise.resolve({ data: {} });
    });

    render(<App />);
    const user = userEvent.setup();

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/auth/me'));
    expect(screen.getByText(/Select your league to enter/i)).toBeInTheDocument();

    await user.click(await screen.findByText('Dynasty Five'));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/leagues/join', null, {
        params: { league_id: 5 },
      });
      expect(localStorage.getItem('fantasyLeagueId')).toBe('5');
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });
  });

  test('visiting /playoffs renders playoff bracket', async () => {
    localStorage.setItem('fantasyToken', 'fake-token');
    localStorage.setItem('fantasyLeagueId', '1');
    apiClient.get.mockResolvedValue({ data: { user_id: 1, username: 'bob', league_id: 1 } });
    // pre-set url before render (router will pick it up)
    window.history.pushState({}, 'Playoffs', '/playoffs');

    render(<App />);
    // ensure auth fetch happens
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/auth/me'));
    expect(await screen.findByText('PlayoffBracket')).toBeInTheDocument();
  });
});
