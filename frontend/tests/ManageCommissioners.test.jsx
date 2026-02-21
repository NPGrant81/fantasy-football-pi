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
import ManageCommissioners from '../src/pages/admin/ManageCommissioners';

function renderPage() {
  return render(
    <MemoryRouter>
      <ManageCommissioners />
    </MemoryRouter>
  );
}

describe('ManageCommissioners', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('updates a commissioner row through the admin endpoint', async () => {
    apiClient.get.mockResolvedValue({
      data: [
        {
          id: 21,
          username: 'Comm A',
          email: 'comma@test.com',
          league_id: 1,
          is_superuser: false,
        },
      ],
    });
    apiClient.put.mockResolvedValue({ data: { message: 'Commissioner updated.' } });

    renderPage();

    const nameInput = await screen.findByDisplayValue('Comm A');
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, 'Comm Alpha');

    await userEvent.click(screen.getByRole('button', { name: /Update/i }));

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('/admin/tools/commissioners/21', {
        username: 'Comm Alpha',
        email: 'comma@test.com',
        league_id: 1,
      });
    });
  });

  test('removes commissioner access after confirmation', async () => {
    apiClient.get.mockResolvedValue({
      data: [
        {
          id: 21,
          username: 'Comm A',
          email: 'comma@test.com',
          league_id: 1,
          is_superuser: false,
        },
      ],
    });
    apiClient.delete.mockResolvedValue({ data: { message: 'Commissioner access removed.' } });
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderPage();

    const removeButton = await screen.findByRole('button', { name: /Remove Access/i });
    await userEvent.click(removeButton);

    await waitFor(() => {
      expect(apiClient.delete).toHaveBeenCalledWith('/admin/tools/commissioners/21');
      expect(screen.queryByDisplayValue('Comm A')).not.toBeInTheDocument();
    });
  });

  test('adds commissioner and shows invite details', async () => {
    let commissioners = [
      {
        id: 21,
        username: 'Comm A',
        email: 'comma@test.com',
        league_id: 1,
        is_superuser: false,
      },
    ];

    apiClient.get.mockImplementation(() => Promise.resolve({ data: commissioners }));

    apiClient.post.mockImplementation(() => {
      commissioners = [
        ...commissioners,
        {
          id: 22,
          username: 'Comm B',
          email: 'commb@test.com',
          league_id: 2,
          is_superuser: false,
        },
      ];

      return Promise.resolve({
        data: {
          message: 'Commissioner invited.',
          league_id: 2,
          debug_password: 'Comm1234',
        },
      });
    });

    renderPage();

    await userEvent.type(
      await screen.findByPlaceholderText('Commissioner name'),
      'Comm B'
    );
    await userEvent.type(screen.getByPlaceholderText('Email address'), 'commb@test.com');
    await userEvent.type(screen.getByPlaceholderText('League ID (optional)'), '2');

    await userEvent.click(screen.getByRole('button', { name: /Send Invite/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/admin/tools/commissioners', {
        username: 'Comm B',
        email: 'commb@test.com',
        league_id: 2,
      });
      expect(screen.getByText(/League ID: 2/i)).toBeInTheDocument();
      expect(screen.getByText(/Temporary password: Comm1234/i)).toBeInTheDocument();
    });
  });
});
