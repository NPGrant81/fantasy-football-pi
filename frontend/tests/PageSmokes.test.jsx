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
import SiteAdmin from '../src/pages/admin/SiteAdmin';
import apiClient from '../src/api/client';

describe('DraftBoard (Smoke Test)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  test('renders without crashing', () => {
    apiClient.get.mockResolvedValue({ data: {} });
    apiClient.post.mockResolvedValue({ data: {} });

    const { container } = render(
      <DraftBoard token="test-token" activeOwnerId={1} activeLeagueId={1} />
    );

    expect(container).toBeInTheDocument();
  });

  test('handles missing props gracefully', () => {
    const { container } = render(<DraftBoard />);
    expect(container).toBeInTheDocument();
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

    // Component should attempt to load admin data
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalled();
    });
  });
});
