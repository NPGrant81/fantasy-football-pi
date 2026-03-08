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
      if (url === '/keepers/') {
        return Promise.resolve({
          data: {
            selections: [],
            recommended: [
              { player_id: 10, surplus: 30, keep_cost: 5, projected_value: 35 },
            ],
            selected_count: 0,
            max_allowed: 3,
            estimated_budget: 200,
            effective_budget: 200,
          },
        });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({
          data: {
            roster: [
              {
                player_id: 10,
                name: 'Alice',
                draft_price: 20,
                projected_value: 40,
              },
            ],
          },
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
    // recommended surplus should be shown
    expect(screen.getByText(/Recommended surplus/i)).toBeInTheDocument();
    // the slot grid cell should also have a star indicating recommendation
    expect(screen.getByText('★')).toBeInTheDocument();

    // initial budget should equal 200
    expect(screen.getByText(/Estimated Budget: \$200/)).toBeInTheDocument();
  });

  test('ineligible players are disabled', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/keepers/') {
        return Promise.resolve({
          data: {
            selections: [],
            recommended: [],
            selected_count: 0,
            max_allowed: 3,
            estimated_budget: 100,
            effective_budget: 100,
            ineligible: [10],
          },
        });
      }
      if (url.startsWith('/team/1?week=')) {
        return Promise.resolve({
          data: { roster: [{ player_id: 10, name: 'Alice', draft_price: 5 }] },
        });
      }
      return Promise.reject(new Error('unknown'));
    });

    render(<Keepers />);
    await waitFor(() => screen.getByText('Alice'));
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).toBeDisabled();
    expect(screen.getByTitle('Reached max keeper years')).toBeInTheDocument();
  });

  test('toggle player and submit', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/keepers/') {
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
          data: {
            roster: [
              {
                player_id: 10,
                name: 'Alice',
                draft_price: 20,
                projected_value: 40,
              },
            ],
          },
        });
      }
      return Promise.reject(new Error('unknown'));
    });
    apiClient.post.mockResolvedValue({ data: {} });

    render(<Keepers />);
    await waitFor(() => screen.getByText('Alice'));
    // draft price should be displayed
    expect(screen.getByText(/draft: \$20/)).toBeInTheDocument();
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);
    // budget updated (draft_price 20 subtracted from 100)
    expect(screen.getByText(/Estimated Budget: \$80/)).toBeInTheDocument();
    // clicking slot should also clear selection and restore budget
    fireEvent.click(screen.getByText('Alice'));
    expect(screen.getByText(/Estimated Budget: \$100/)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Submit List/i));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        '/keepers/',
        expect.any(Object)
      )
    );
  });
});
