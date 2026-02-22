import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import DraftBoard from '../src/pages/DraftBoard';
import WaiverWire from '../src/pages/WaiverWire';

// react-router navigation is used in SiteAdmin; mock the hook so we can
// assert it's called instead of allowing an actual router to run.
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

import SiteAdmin from '../src/pages/admin/SiteAdmin';
import apiClient from '../src/api/client';

describe('DraftBoard (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders without crashing', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/owners')) return Promise.resolve({ data: [] });
      if (url === '/players/') return Promise.resolve({ data: [] });
      if (url.startsWith('/draft/history')) return Promise.resolve({ data: [] });
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { draft_year: 2026 } });
      }
      if (url.startsWith('/leagues/1/budgets')) return Promise.resolve({ data: [] });
      if (url === '/auth/me') {
        return Promise.resolve({ data: { is_commissioner: false, username: 'alice' } });
      }
      if (url === '/leagues/1') return Promise.resolve({ data: { name: 'The Big Show' } });
      return Promise.resolve({ data: [] });
    });
    apiClient.post.mockResolvedValue({ data: {} });

    const { container } = render(
      <DraftBoard token="test-token" activeOwnerId={1} activeLeagueId={1} />
    );

    await waitFor(() => {
      expect(container).toBeInTheDocument();
    });
  });

  test('handles missing props gracefully', async () => {
    apiClient.get.mockResolvedValue({ data: [] });
    const { container } = render(<DraftBoard />);
    await waitFor(() => {
      expect(container).toBeInTheDocument();
    });
  });
});

describe('WaiverWire (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders without crashing', async () => {
    apiClient.get.mockResolvedValue({ data: { waiver_claims: [] } });

    const { container } = render(
      <WaiverWire activeOwnerId={1} username="alice" leagueName="The Big Show" />
    );

    await waitFor(() => {
      expect(container).toBeInTheDocument();
    });
  });

  test('handles API errors gracefully', async () => {
    apiClient.get.mockRejectedValue(new Error('API Error'));

    const { container } = render(
      <WaiverWire activeOwnerId={1} username="alice" leagueName="The Big Show" />
    );

    await waitFor(() => {
      expect(container).toBeInTheDocument();
    });
  });
});

describe('SiteAdmin (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders without crashing', () => {
    apiClient.get.mockResolvedValue({ data: {} });

    const { container } = render(<SiteAdmin />);

    expect(container).toBeInTheDocument();
  });

  test('attempts to fetch admin data if available', async () => {
    apiClient.get.mockResolvedValue({ data: { admins: [] } });

    render(<SiteAdmin />);

    await waitFor(() => {
      expect(screen.getByText(/Site Admin/i)).toBeInTheDocument();
    });
  });

  test('clicking the commissioner button uses router navigation', async () => {
    apiClient.get.mockResolvedValue({ data: {} });

    const { getByRole } = render(<SiteAdmin />);
    // find the action button specifically by role + accessible name
    const button = getByRole('button', { name: /Manage Commissioners/i });

    button.click();
    expect(mockNavigate).toHaveBeenCalledWith('/admin/manage-commissioners');
  });
});
