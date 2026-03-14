import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
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

import ManageKeeperRules from '../src/pages/commissioner/ManageKeeperRules';
import apiClient from '../src/api/client';

describe('ManageKeeperRules page', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders loading state and fetches data', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/keepers/settings') {
        return Promise.resolve({
          data: {
            max_keepers: 2,
            max_years_per_player: 1,
            deadline_date: '2026-08-01T00:00:00Z',
            waiver_policy: true,
            trade_deadline: null,
            drafted_only: true,
            cost_type: 'round',
            cost_inflation: 1,
          },
        });
      }
      if (url === '/keepers/admin') {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error('unknown'));
    });

    render(<ManageKeeperRules />);
    await waitFor(() =>
      expect(screen.getByLabelText(/Max Keepers Per Owner/i)).toBeInTheDocument()
    );
    expect(screen.getByDisplayValue('2')).toBeInTheDocument();
    expect(screen.getByLabelText(/Cost Type/i)).toHaveValue('round');
  });

  test('submits updated settings', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/keepers/settings') {
        return Promise.resolve({
          data: {
            max_keepers: 1,
            max_years_per_player: 0,
            deadline_date: '',
            waiver_policy: false,
            trade_deadline: '',
            drafted_only: false,
            cost_type: 'round',
            cost_inflation: 0,
          },
        });
      }
      if (url === '/keepers/admin') {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: [] });
    });
    apiClient.put.mockResolvedValue({ data: {} });

    render(<ManageKeeperRules />);
    await waitFor(() => screen.getByLabelText(/Max Keepers Per Owner/i));

    fireEvent.change(screen.getByLabelText(/Max Keepers Per Owner/i), {
      target: { value: '3' },
    });
    fireEvent.change(screen.getByLabelText(/Cost Inflation/i), {
      target: { value: '2' },
    });
    fireEvent.click(screen.getByText(/Update Settings/i));

    await waitFor(() =>
      expect(apiClient.put).toHaveBeenCalledWith('/keepers/settings',
        expect.objectContaining({
          max_keepers: 3,
          cost_inflation: 2,
        })
      )
    );
  });

  test('veto and reset actions', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/keepers/settings') {
        return Promise.resolve({ data: { max_keepers: 1 } });
      }
      if (url === '/keepers/admin') {
        return Promise.resolve({
          data: [
            { owner_id: 5, username: 'owner5', selections: [] },
          ],
        });
      }
      return Promise.resolve({ data: [] });
    });
    apiClient.post.mockResolvedValue({ data: {} });

    render(<ManageKeeperRules />);
    await waitFor(() => {
      expect(screen.getAllByText(/owner5/i).length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByText(/Veto/i));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith('/keepers/admin/5/veto')
    );

    // simulate clicking reset and confirming
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    fireEvent.click(screen.getByText(/Reset All Keepers/i));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith('/keepers/admin/reset')
    );
  });
});
