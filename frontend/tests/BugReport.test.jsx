import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

import apiClient from '../src/api/client';
import BugReport from '../src/pages/BugReport';

function renderPage() {
  return render(
    <MemoryRouter>
      <BugReport />
    </MemoryRouter>
  );
}

describe('BugReport', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.history.pushState({}, '', '/bug-report');
    apiClient.get.mockResolvedValue({ data: { email: 'owner@example.com' } });
  });

  test('submits a bug report and shows loading state', async () => {
    let resolvePost;
    apiClient.put.mockResolvedValue({ data: { ok: true } });
    apiClient.post.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePost = resolve;
        })
    );

    renderPage();

    await userEvent.type(await screen.findByPlaceholderText(/Short summary/i), 'Draft board flickers');
    await userEvent.type(
      screen.getByPlaceholderText(/Steps to reproduce/i),
      'Open draft page and refresh twice.'
    );

    await userEvent.click(screen.getByRole('button', { name: /Submit Bug Report/i }));

    expect(screen.getByRole('button', { name: /Submitting/i })).toBeDisabled();
    expect(screen.getByPlaceholderText(/Short summary/i)).toBeDisabled();

    resolvePost({ data: { issue_url: 'https://github.com/NPGrant81/fantasy-football-pi/issues/999' } });

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('/auth/email', {
        email: 'owner@example.com',
      });
      expect(apiClient.post).toHaveBeenCalledWith('/feedback/bug',
        expect.objectContaining({
          title: 'Draft board flickers',
          description: 'Open draft page and refresh twice.',
          page_url: '/bug-report',
          issue_type: 'bug',
          contact_email: 'owner@example.com',
        })
      );
      expect(
        screen.getByText(/Bug report submitted and GitHub issue created/i)
      ).toBeInTheDocument();
    });
  });

  test('shows retry action after failure and retries submit', async () => {
    apiClient.put.mockResolvedValue({ data: { ok: true } });
    apiClient.post
      .mockRejectedValueOnce({ response: { data: { detail: 'Network timeout' } } })
      .mockResolvedValueOnce({ data: {} });

    renderPage();

    await userEvent.type(await screen.findByPlaceholderText(/Short summary/i), 'Page crashes');
    await userEvent.type(screen.getByPlaceholderText(/Steps to reproduce/i), 'Click save quickly.');

    await userEvent.click(screen.getByRole('button', { name: /Submit Bug Report/i }));

    await waitFor(() => {
      expect(screen.getByText(/Network timeout/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Retry Submit/i })).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole('button', { name: /Retry Submit/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledTimes(2);
      expect(screen.getByText(/Bug report submitted\. Thank you/i)).toBeInTheDocument();
    });
  });
});
