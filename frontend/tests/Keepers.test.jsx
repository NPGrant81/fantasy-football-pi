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
    localStorage.setItem('user_id', '1');
  });

  test('renders loading state', () => {
    apiClient.get.mockImplementation(() => new Promise(() => {}));
    render(<Keepers />);
    expect(screen.getByText(/Loading keepers/i)).toBeInTheDocument();
  });

  test('fetches keeper data and roster', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/keepers') {
        return Promise.resolve({
          data: {
            selections: [],
            recommended: [],
            selected_count: 0,
            max_allowed: 3,
            estimated_budget: 200,
            effective_budget: 200,
          },
        });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({
          data: { roster: [{ player_id: 10, name: 'Alice' }] },
        });
      }
      return Promise.reject(new Error('unknown'));
    });

    render(<Keepers />);
    await waitFor(() =>
      expect(screen.getByText(/Manage Keepers/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/Estimated Budget/i)).toBeInTheDocument();
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
    expect(screen.queryByText(/Recommended:/i)).not.toBeInTheDocument();
  });

  test('toggle player and submit', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/keepers') {
        return Promise.resolve({
          data: {
            selections: [],
            recommended: [],
            selected_count: 0,
            max_allowed: 1,
            estimated_budget: 100,
            effective_budget: 100,
          },
        });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({
          data: { roster: [{ player_id: 10, name: 'Alice' }] },
        });
      }
      return Promise.reject(new Error('unknown'));
    });
    apiClient.post.mockResolvedValue({ data: {} });

    render(<Keepers />);
    await waitFor(() => screen.getByText('Alice'));
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByText(/Submit List/i));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        '/keepers',
        expect.any(Object)
      )
    );
  });
});
