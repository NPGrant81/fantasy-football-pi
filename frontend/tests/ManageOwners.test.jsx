import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import apiClient from '../src/api/client';
import ManageOwners from '../src/pages/commissioner/ManageOwners';

function renderPage() {
  return render(
    <MemoryRouter>
      <ManageOwners />
    </MemoryRouter>
  );
}

describe('ManageOwners', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('fantasyLeagueId', '1');
    vi.resetAllMocks();
  });

  test('updates an owner row through the owners endpoint', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1/settings') {
        return Promise.resolve({
          data: { roster_size: 14, salary_cap: 200, starting_slots: { OWNER_LIMIT: 12 }, scoring_rules: [] },
        });
      }
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({
          data: [{ id: 10, username: 'Alice', email: 'alice@test.com' }],
        });
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
    apiClient.put.mockResolvedValue({ data: { message: 'Owner updated.' } });

    renderPage();

    const nameInput = await screen.findByDisplayValue('Alice');
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'Alicia');

    const updateButton = screen.getByRole('button', { name: /Update/i });
    await userEvent.click(updateButton);

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('/leagues/owners/10', {
        username: 'Alicia',
        email: 'alice@test.com',
      });
    });
  });

  test('removes an owner after confirmation', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1/settings') {
        return Promise.resolve({
          data: { roster_size: 14, salary_cap: 200, starting_slots: { OWNER_LIMIT: 12 }, scoring_rules: [] },
        });
      }
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({
          data: [{ id: 10, username: 'Alice', email: 'alice@test.com' }],
        });
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
    apiClient.delete.mockResolvedValue({ data: { message: 'User removed from league.' } });
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderPage();

    const removeButton = await screen.findByRole('button', { name: /Remove/i });
    await userEvent.click(removeButton);

    await waitFor(() => {
      expect(apiClient.delete).toHaveBeenCalledWith('/leagues/1/members/10');
      expect(screen.queryByDisplayValue('Alice')).not.toBeInTheDocument();
    });
  });

  test('adds owner with league id and displays invite details', async () => {
    let owners = [{ id: 10, username: 'Alice', email: 'alice@test.com' }];

    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1/settings') {
        return Promise.resolve({
          data: { roster_size: 14, salary_cap: 200, starting_slots: { OWNER_LIMIT: 12 }, scoring_rules: [] },
        });
      }
      if (url === '/leagues/owners?league_id=1') {
        return Promise.resolve({ data: owners });
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });

    apiClient.post.mockImplementation(() => {
      owners = [
        ...owners,
        { id: 11, username: 'Bob', email: 'bob@test.com' },
      ];
      return Promise.resolve({
        data: { message: 'Invite sent', league_id: 1, debug_password: 'Temp1234' },
      });
    });

    renderPage();

    await userEvent.type(await screen.findByPlaceholderText('Owner name'), 'Bob');
    await userEvent.type(screen.getByPlaceholderText('Email address'), 'bob@test.com');
    await userEvent.click(screen.getByRole('button', { name: /Send Invite/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/leagues/owners', {
        username: 'Bob',
        email: 'bob@test.com',
        league_id: 1,
      });
      expect(screen.getByText(/League ID: 1/i)).toBeInTheDocument();
      expect(screen.getByText(/Temporary password: Temp1234/i)).toBeInTheDocument();
    });
  });
});
