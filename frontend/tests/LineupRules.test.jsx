import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock('react-router-dom', () => ({
  Link: ({ to, children, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

import LineupRules from '../src/pages/commissioner/LineupRules';
import apiClient from '../src/api/client';

const BASE_SLOTS = {
  QB: 1,
  RB: 2,
  WR: 2,
  TE: 1,
  K: 1,
  DEF: 1,
  FLEX: 1,
  ACTIVE_ROSTER_SIZE: 9,
  MAX_QB: 3,
  MAX_RB: 5,
  MAX_WR: 5,
  MAX_TE: 3,
  MAX_K: 1,
  MAX_DEF: 1,
  MAX_FLEX: 1,
  TAXI_SIZE: 0,
  ALLOW_PARTIAL_LINEUP: 0,
  REQUIRE_WEEKLY_SUBMIT: 1,
};

const BASE_CONFIG = {
  league_id: 1,
  scoring_rules: [],
  starting_slots: BASE_SLOTS,
};

function slotsWithoutExplicitKeys(slots) {
  const next = { ...slots };
  delete next.K;
  delete next.FLEX;
  delete next.DEF;
  return next;
}

describe('LineupRules', () => {
  beforeEach(() => {
    localStorage.setItem('fantasyLeagueId', '1');
    vi.resetAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  test('renders loading state initially', () => {
    apiClient.get.mockImplementation(() => new Promise(() => {}));
    render(<LineupRules />);
    expect(screen.getByText(/loading lineup rules/i)).toBeInTheDocument();
  });

  test('loads and displays commissioner-configured values', async () => {
    apiClient.get.mockResolvedValueOnce({ data: BASE_CONFIG });
    render(<LineupRules />);
    await waitFor(() => {
      expect(screen.getByText(/Total Active Roster Required/i)).toBeInTheDocument();
      expect(screen.getByText(/Save Lineup Rules/i)).toBeInTheDocument();
    });
  });

  test('save includes K slot-count key matching kEnabled toggle (K enabled)', async () => {
    apiClient.get.mockResolvedValueOnce({
      data: {
        ...BASE_CONFIG,
        starting_slots: slotsWithoutExplicitKeys(BASE_SLOTS),
      },
    });
    apiClient.put.mockResolvedValueOnce({ data: {} });

    render(<LineupRules />);
    await waitFor(() =>
      expect(screen.getByText(/Save Lineup Rules/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/Save Lineup Rules/i));

    await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));

    const [, payload] = apiClient.put.mock.calls[0];
    const slots = payload.starting_slots;
    // K slot-count key must be explicitly reintroduced even if omitted in payload.
    expect(slots.K).toBe(1);
    expect(slots.MAX_K).toBe(1);
  });

  test('save includes K slot-count = 0 when K is disabled', async () => {
    const configWithKDisabled = {
      ...BASE_CONFIG,
      starting_slots: { ...BASE_SLOTS, MAX_K: 0, K: 0 },
    };
    apiClient.get.mockResolvedValueOnce({ data: configWithKDisabled });
    apiClient.put.mockResolvedValueOnce({ data: {} });

    render(<LineupRules />);
    await waitFor(() =>
      expect(screen.getByText(/Save Lineup Rules/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/Save Lineup Rules/i));

    await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));

    const [, payload] = apiClient.put.mock.calls[0];
    const slots = payload.starting_slots;
    expect(slots.K).toBe(0);
    expect(slots.MAX_K).toBe(0);
  });

  test('save includes FLEX slot-count key matching flexEnabled toggle', async () => {
    apiClient.get.mockResolvedValueOnce({ data: BASE_CONFIG });
    apiClient.put.mockResolvedValueOnce({ data: {} });

    render(<LineupRules />);
    await waitFor(() =>
      expect(screen.getByText(/Save Lineup Rules/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/Save Lineup Rules/i));

    await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));

    const [, payload] = apiClient.put.mock.calls[0];
    const slots = payload.starting_slots;
    expect(slots.FLEX).toBe(1);
    expect(slots.MAX_FLEX).toBe(1);
  });

  test('save includes FLEX slot-count = 0 when FLEX is disabled', async () => {
    const configWithFlexDisabled = {
      ...BASE_CONFIG,
      starting_slots: { ...BASE_SLOTS, MAX_FLEX: 0, FLEX: 0 },
    };
    apiClient.get.mockResolvedValueOnce({ data: configWithFlexDisabled });
    apiClient.put.mockResolvedValueOnce({ data: {} });

    render(<LineupRules />);
    await waitFor(() =>
      expect(screen.getByText(/Save Lineup Rules/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/Save Lineup Rules/i));

    await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));

    const [, payload] = apiClient.put.mock.calls[0];
    const slots = payload.starting_slots;
    expect(slots.FLEX).toBe(0);
    expect(slots.MAX_FLEX).toBe(0);
  });

  test('save payload contains DEF slot-count key', async () => {
    apiClient.get.mockResolvedValueOnce({ data: BASE_CONFIG });
    apiClient.put.mockResolvedValueOnce({ data: {} });

    render(<LineupRules />);
    await waitFor(() =>
      expect(screen.getByText(/Save Lineup Rules/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/Save Lineup Rules/i));

    await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));

    const [, payload] = apiClient.put.mock.calls[0];
    expect(payload.starting_slots.DEF).toBe(1);
    expect(payload.starting_slots.MAX_DEF).toBe(1);
  });

  test('shows success message after save', async () => {
    apiClient.get.mockResolvedValueOnce({ data: BASE_CONFIG });
    apiClient.put.mockResolvedValueOnce({ data: {} });

    render(<LineupRules />);
    await waitFor(() =>
      expect(screen.getByText(/Save Lineup Rules/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByText(/Save Lineup Rules/i));

    await waitFor(() =>
      expect(screen.getByText(/Lineup rules saved/i)).toBeInTheDocument()
    );
  });

  test('shows error when no league is selected', async () => {
    localStorage.removeItem('fantasyLeagueId');

    render(<LineupRules />);

    await waitFor(() =>
      expect(
        screen.getByText(/No active league selected/i)
      ).toBeInTheDocument()
    );
  });
});
