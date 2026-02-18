import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

vi.mock('react-router-dom', () => ({
  Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
}));

import Sidebar from '../src/components/Sidebar';

describe('Sidebar (Navigation)', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    username: 'alice',
    leagueId: 1,
  };

  test('renders when isOpen is true', () => {
    render(<Sidebar {...defaultProps} />);
    expect(screen.getByText(/Menu/i)).toBeInTheDocument();
  });

  test('does not render when isOpen is false', () => {
    render(<Sidebar {...defaultProps} isOpen={false} />);
    expect(screen.queryByText(/Menu/i)).not.toBeInTheDocument();
  });

  test('displays username in sidebar', () => {
    render(<Sidebar {...defaultProps} username="testuser" />);
    expect(screen.getByText(/testuser/i)).toBeInTheDocument();
  });

  test('has navigation links to main pages', () => {
    render(<Sidebar {...defaultProps} />);

    expect(screen.getByText(/Home/i)).toBeInTheDocument();
    expect(screen.getByText(/War Room/i)).toBeInTheDocument(); // Draft
    expect(screen.getByText(/My Team/i)).toBeInTheDocument();
    expect(screen.getByText(/Matchups/i)).toBeInTheDocument();
    expect(screen.getByText(/Waiver Wire/i)).toBeInTheDocument();
  });

  test('navigation links point to correct routes', () => {
    render(<Sidebar {...defaultProps} />);

    const homeLink = screen.getByText(/Home/).closest('a');
    expect(homeLink).toHaveAttribute('href', '/');

    const draftLink = screen.getByText(/War Room/).closest('a');
    expect(draftLink).toHaveAttribute('href', '/draft');

    const teamLink = screen.getByText(/My Team/).closest('a');
    expect(teamLink).toHaveAttribute('href', '/team');
  });

  test('has settings section', () => {
    render(<Sidebar {...defaultProps} />);
    expect(screen.getByText(/Settings/i)).toBeInTheDocument();
  });

  test('calls onClose when navigation link is clicked', async () => {
    const onClose = vi.fn();
    render(<Sidebar {...defaultProps} onClose={onClose} />);

    const user = userEvent.setup();
    const homeLink = screen.getByText(/Home/).closest('a');
    await user.click(homeLink);

    expect(onClose).toHaveBeenCalled();
  });

  test('has close button (X icon)', () => {
    render(<Sidebar {...defaultProps} />);
    const closeButtons = screen.getAllByRole('button');
    expect(closeButtons.length).toBeGreaterThan(0);
  });

  test('close button calls onClose', async () => {
    const onClose = vi.fn();
    render(<Sidebar {...defaultProps} onClose={onClose} />);

    const user = userEvent.setup();
    const closeButtons = screen.getAllByRole('button');
    await user.click(closeButtons[0]);

    expect(onClose).toHaveBeenCalled();
  });
});
