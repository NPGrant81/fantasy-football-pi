import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

// Mock child components to keep App render surface-level and deterministic
vi.mock('../src/components/Layout', () => ({
  default: ({ children }) => <div data-testid="layout">{children}</div>,
}));
vi.mock('../src/pages/Dashboard', () => ({
  default: () => <div>Dashboard</div>,
}));
vi.mock('../src/pages/DraftBoard', () => ({ default: () => <div>Draft</div> }));
vi.mock('../src/pages/MyTeam', () => ({ default: () => <div>MyTeam</div> }));
vi.mock('../src/pages/Matchups', () => ({
  default: () => <div>Matchups</div>,
}));
vi.mock('../src/pages/GameCenter', () => ({
  default: () => <div>GameCenter</div>,
}));
vi.mock('../src/pages/CommissionerDashboard', () => ({
  default: () => <div>Commissioner</div>,
}));
vi.mock('../src/pages/WaiverWire', () => ({
  default: () => <div>Waivers</div>,
}));
vi.mock('../src/pages/SiteAdmin', () => ({ default: () => <div>Admin</div> }));

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
    expect(screen.getByText(/WAR ROOM LOGIN/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Enter username/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Enter password/i)).toBeInTheDocument();
  });

  test('uses token to fetch /auth/me and shows app when valid', async () => {
    localStorage.setItem('fantasyToken', 'fake-token');
    apiClient.get.mockResolvedValue({
      data: { user_id: 7, username: 'alice' },
    });

    render(<App />);

    // Wait for effect to run and children to render inside Layout
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/auth/me'));
    expect(localStorage.getItem('fantasyToken')).toBe('fake-token');
    expect(screen.getByTestId('layout')).toBeInTheDocument();
  });
});
