import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}));

vi.mock('react-router-dom', () => ({
  Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
}));

import Sidebar from '../src/components/Sidebar';
import apiClient from '../src/api/client';

describe('Sidebar (Navigation)', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    username: 'alice',
    leagueId: 1,
  };

  beforeEach(() => {
    vi.resetAllMocks();
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/1') {
        return Promise.resolve({ data: { name: 'The Big Show' } });
      }
      if (url === '/auth/me') {
        return Promise.resolve({ data: { is_commissioner: false } });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
  });

  const renderSidebar = async (props = {}) => {
    render(<Sidebar {...defaultProps} {...props} />);
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    });
  };

  test('renders when isOpen is true', async () => {
    await renderSidebar();
    expect(screen.getByText(/FANTASY/i)).toBeInTheDocument();
  });

  test('does not render when isOpen is false', async () => {
    await renderSidebar({ isOpen: false });
    expect(screen.queryByText(/Menu/i)).not.toBeInTheDocument();
  });

  test('displays username in sidebar', async () => {
    await renderSidebar({ username: 'testuser' });
    expect(screen.getByText(/testuser/i)).toBeInTheDocument();
  });

  test('has navigation links to main pages', async () => {
    await renderSidebar();

    expect(screen.getByText(/Home/i)).toBeInTheDocument();
    expect(screen.getByText(/War Room/i)).toBeInTheDocument(); // Draft
    expect(screen.getByText(/My Team/i)).toBeInTheDocument();
    expect(screen.getByText(/Matchups/i)).toBeInTheDocument();
    expect(screen.getByText(/Waiver Wire/i)).toBeInTheDocument();
  });

  test('navigation links point to correct routes', async () => {
    await renderSidebar();

    const homeLink = screen.getByText(/Home/).closest('a');
    expect(homeLink).toHaveAttribute('href', '/');

    const draftLink = screen.getByText(/War Room/).closest('a');
    expect(draftLink).toHaveAttribute('href', '/draft');

    const teamLink = screen.getByText(/My Team/).closest('a');
    expect(teamLink).toHaveAttribute('href', '/team');
  });

  test('has settings section', async () => {
    await renderSidebar();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  test('calls onClose when navigation link is clicked', async () => {
    const onClose = vi.fn();
    await renderSidebar({ onClose });

    const user = userEvent.setup();
    const homeLink = screen.getByText(/Home/).closest('a');
    await user.click(homeLink);

    expect(onClose).toHaveBeenCalled();
  });

  test('has close button (X icon)', async () => {
    await renderSidebar();
    const closeButtons = screen.getAllByRole('button');
    expect(closeButtons.length).toBeGreaterThan(0);
  });

  test('close button calls onClose', async () => {
    const onClose = vi.fn();
    await renderSidebar({ onClose });

    const user = userEvent.setup();
    const closeButtons = screen.getAllByRole('button');
    await user.click(closeButtons[0]);

    expect(onClose).toHaveBeenCalled();
  });
});
