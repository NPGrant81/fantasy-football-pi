import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(), // added for settings updates
  },
}));

import DraftBoard from '../src/pages/DraftBoard';
import WaiverWire from '../src/pages/WaiverWire';
import WaiverRules from '../src/pages/WaiverRules';

// react-router navigation is used in SiteAdmin; mock the hook so we can
// assert it's called instead of allowing an actual router to run.
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

import ManageWaiverRules from '../src/pages/commissioner/ManageWaiverRules';
import SiteAdmin from '../src/pages/admin/SiteAdmin';
import CommishAdmin from '../src/pages/commissioner/CommishAdmin';
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
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/The Big Show') return Promise.resolve({ data: { draft_status: 'PRE_DRAFT' } });
      if (url === '/leagues/The Big Show/settings')
        return Promise.resolve({ data: { waiver_deadline: '2026-09-01' } });
      return Promise.resolve({ data: [] });
    });

    const { container } = render(
      <WaiverWire activeOwnerId={1} username="alice" leagueName="The Big Show" />
    );

    await waitFor(() => {
      expect(container).toBeInTheDocument();
    });
  });

  test('shows deadline when provided', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/leagues/The Big Show') return Promise.resolve({ data: { draft_status: 'PRE_DRAFT' } });
      if (url === '/leagues/The Big Show/settings')
        return Promise.resolve({ data: { waiver_deadline: '2026-09-01' } });
      if (url === '/players/waiver-wire') return Promise.resolve({ data: [] });
      if (url.startsWith('/dashboard/')) return Promise.resolve({ data: { roster: [] } });
      return Promise.resolve({ data: [] });
    });

    render(<WaiverWire activeOwnerId={1} username="alice" leagueName="The Big Show" />);

    await waitFor(() => {
      expect(screen.getByText(/Waiver Deadline/i)).toBeInTheDocument();
      expect(screen.getByText(/View waiver rules/i)).toBeInTheDocument();
    });
  });

  // new WaiverRules tests
  describe('WaiverRules (Smoke Test)', () => {
    beforeEach(() => {
      localStorage.clear();
      vi.resetAllMocks();
    });

    test('renders rules read-only for normal user', async () => {
      apiClient.get.mockImplementation((url) => {
        if (url === '/auth/me') return Promise.resolve({ data: { is_commissioner: false } });
        if (url === '/leagues/1/settings')
          return Promise.resolve({ data: { waiver_deadline: 'D', roster_size: 12 } });
        return Promise.resolve({ data: {} });
      });

      const { getByText, queryByText } = render(<WaiverRules leagueId={1} />);
      await waitFor(() => {
        expect(getByText(/Waiver Wire Rules/i)).toBeInTheDocument();
        expect(getByText(/Waiver Deadline/i)).toBeInTheDocument();
        expect(getByText(/Starting FAAB Budget/i)).toBeInTheDocument();
        expect(getByText(/Waiver System/i)).toBeInTheDocument();
        expect(getByText(/Tie-breaker/i)).toBeInTheDocument();
        expect(getByText(/12/)).toBeInTheDocument(); // roster size always shown
      });
      expect(queryByText(/Edit Waiver Rules/i)).toBeNull();
    });

    test('shows edit button for commissioner', async () => {
      apiClient.get.mockImplementation((url) => {
        if (url === '/auth/me') return Promise.resolve({ data: { is_commissioner: true } });
        if (url === '/leagues/1/settings')
          return Promise.resolve({ data: { waiver_deadline: 'X', roster_size: 14 } });
        return Promise.resolve({ data: {} });
      });

      const { getByText } = render(<WaiverRules leagueId={1} />);
      await waitFor(() => {
        expect(getByText(/Edit Waiver Rules/i)).toBeInTheDocument();
        expect(getByText(/Waiver Deadline/i)).toBeInTheDocument();
        expect(getByText(/Trade Deadline/i)).toBeInTheDocument();
      });
      fireEvent.click(getByText(/Edit Waiver Rules/i));
      expect(mockNavigate).toHaveBeenCalledWith('/commissioner/manage-waiver-rules');
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

describe('ManageWaiverRules (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders without crashing and shows existing settings', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { waiver_deadline: '2026-09-01', starting_waiver_budget: 100, waiver_system: 'FAAB', waiver_tiebreaker: 'standings', roster_size: 14 } });
      }
      if (url === '/waivers/claims') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/leagues/1/waiver-budgets') {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: [] });
    });
    apiClient.put.mockResolvedValue({ data: {} });

    const { container, getByLabelText } = render(<ManageWaiverRules />);
    await waitFor(() => {
      expect(container).toBeInTheDocument();
      expect(getByLabelText(/Roster Size Limit/i)).toBeInTheDocument();
      expect(getByLabelText(/Starting FAAB Budget/i)).toBeInTheDocument();
      expect(screen.getByText(/Owner ID/i)).toBeInTheDocument();
    });
  });

  test('allows updating waiver deadline', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { waiver_deadline: 'old', starting_waiver_budget: 120, waiver_system: 'PRIORITY', waiver_tiebreaker: 'priority', roster_size: 16 } });
      }
      if (url === '/waivers/claims') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/leagues/1/waiver-budgets') {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: [] });
    });
    apiClient.put.mockResolvedValue({ data: {} });

    const { getByLabelText, getByText } = render(<ManageWaiverRules />);
    await waitFor(() => expect(getByLabelText(/Waiver Deadline/i)).toBeInTheDocument());
    expect(getByLabelText(/Roster Size Limit/i).value).toBe('16');
    fireEvent.change(getByLabelText(/Waiver Deadline/i), { target: { value: 'new-deadline' } });
    fireEvent.change(getByLabelText(/Starting FAAB Budget/i), { target: { value: '150' } });
    fireEvent.change(getByLabelText(/Waiver System/i), { target: { value: 'BOTH' } });
    fireEvent.change(getByLabelText(/Tie-breaker/i), { target: { value: 'timestamp' } });
    fireEvent.change(getByLabelText(/Roster Size Limit/i), { target: { value: '18' } });
    fireEvent.click(getByText(/Update Waiver Rules/i));
    await waitFor(() => expect(getByText(/Waiver rules updated!/i)).toBeInTheDocument());
    expect(apiClient.put).toHaveBeenCalledWith(
      '/leagues/1/settings',
      expect.objectContaining({ waiver_deadline: 'new-deadline', starting_waiver_budget: 150, waiver_system: 'BOTH', waiver_tiebreaker: 'timestamp', roster_size: 18 })
    );
  });

  test('renders claim history rows when data provided', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url.startsWith('/leagues/1/settings')) {
        return Promise.resolve({ data: { waiver_deadline: 'x' } });
      }
      if (url === '/waivers/claims') {
        return Promise.resolve({ data: [
          { id: 1, username: 'bob', player_name: 'Alice', drop_player_name: null, bid_amount: 5, status: 'PENDING' }
        ] });
      }
      return Promise.resolve({ data: [] });
    });

    render(<ManageWaiverRules />);
    await waitFor(() => expect(screen.getByText('bob')).toBeInTheDocument());
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('PENDING')).toBeInTheDocument();
  });
});

describe('CommishAdmin (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('button to waiver rules uses navigation', () => {
    const { getByText } = render(<CommishAdmin />);
    fireEvent.click(getByText(/WAIVER RULES/i));
    expect(mockNavigate).toHaveBeenCalledWith('/waiver-rules');
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
