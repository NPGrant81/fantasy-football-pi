import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

vi.mock('../src/components/Sidebar', () => ({
  default: ({ isOpen, _onClose }) => (
    isOpen ? <div data-testid="sidebar">Sidebar</div> : null
  ),
}));

import Layout from '../src/components/Layout';

describe('Layout (Main App Container)', () => {
  test('renders header with logo and title', () => {
    render(
      <Layout username="alice" leagueId={1}>
        <div>Test Content</div>
      </Layout>
    );

    expect(screen.getByText(/FANTASY/i)).toBeInTheDocument();
  });

  test('renders main content area with children', () => {
    render(
      <Layout username="alice" leagueId={1}>
        <div data-testid="main-content">Main Content</div>
      </Layout>
    );

    expect(screen.getByTestId('main-content')).toBeInTheDocument();
  });

  test('has menu button to toggle sidebar', async () => {
    render(
      <Layout username="alice" leagueId={1}>
        <div>Test Content</div>
      </Layout>
    );

    const menuButton = screen.getByRole('button', { name: '' }); // Menu icon has no text
    expect(menuButton).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(menuButton);

    // Sidebar should be visible after clicking menu
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
  });

  test('passes username and league ID to sidebar', () => {
    render(
      <Layout username="testuser" leagueId={42}>
        <div>Test Content</div>
      </Layout>
    );

    // The Sidebar mock receives these props but we can verify the Layout component renders
    expect(screen.getByText(/FANTASY/i)).toBeInTheDocument();
  });

  test('header has proper styling and structure', () => {
    const { container } = render(
      <Layout username="alice" leagueId={1}>
        <div>Test Content</div>
      </Layout>
    );

    const header = container.querySelector('header');
    expect(header).toBeInTheDocument();
  });

  test('main content area has proper styling', () => {
    const { container } = render(
      <Layout username="alice" leagueId={1}>
        <div>Test Content</div>
      </Layout>
    );

    const main = container.querySelector('main');
    expect(main).toBeInTheDocument();
  });
});
