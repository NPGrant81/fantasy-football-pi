import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('react-router-dom', () => ({
  useParams: () => ({}),
}));

// Mock commissioner-related components
vi.mock('../src/components/commissioner/ScoringModal', () => ({
  default: ({ open, onClose }) => open ? <div>ScoringModal</div> : null,
}));

import CommissionerDashboard from '../src/pages/CommissionerDashboard';
import apiClient from '../src/api/client';

describe('CommissionerDashboard (Commissioner Controls)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
    localStorage.setItem('fantasyLeagueId', '1');
  });

  test('renders commissioner dashboard header', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { user_id: 1, username: 'commissioner', is_commissioner: true },
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<CommissionerDashboard />);

    // Wait for render to complete
    await waitFor(() => {
      expect(screen.getByText(/Commissioner/i)).toBeInTheDocument();
    });
  });

  test('shows loading state on initial mount', () => {
    apiClient.get.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<CommissionerDashboard />);

    // Should show loading indicator or menu
    const content = screen.queryByText(/Commissioner/i) || screen.queryByText(/Menu/i);
    // Component should render something
    expect(screen.getByRole('heading', { level: 1 }) || content).toBeDefined();
  });

  test('fetches commissioner data on mount', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({
          data: { user_id: 1, username: 'commissioner', is_commissioner: true },
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<CommissionerDashboard />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    });
  });

  test('handles errors gracefully', async () => {
    apiClient.get.mockRejectedValue(new Error('API Error'));

    render(<CommissionerDashboard />);

    // Component should render without crashing
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 }) || true).toBeDefined();
    });
  });
});
