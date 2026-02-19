import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('../src/api/client', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
import apiClient from '../src/api/client';
import LeagueAdvisor from '../src/components/LeagueAdvisor';

describe('LeagueAdvisor (chat)', () => {
  beforeAll(() => {
    Element.prototype.scrollIntoView = vi.fn();
  });

  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('opens on toggle and sends message, displays AI response', async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === '/auth/me') {
        return Promise.resolve({ data: { username: 'alice', league_id: 1 } });
      }
      if (url === '/advisor/status') {
        return Promise.resolve({ data: { enabled: true } });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
    apiClient.post.mockResolvedValue({ data: { response: 'Hello from AI' } });
    render(<LeagueAdvisor />);

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/auth/me'));

    // Toggle open
    const toggle = screen.getByRole('button', { name: /🤖/i });
    fireEvent.click(toggle);

    // Type a message into the input
    const input = await screen.findByPlaceholderText(
      /Search players or ask advice/i
    );
    fireEvent.change(input, { target: { value: 'Who should I draft?' } });

    // Submit with Enter key to avoid relying on icon-only button label
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        '/advisor/ask',
        expect.objectContaining({
          user_query: 'Who should I draft?',
        })
      )
    );
    expect(await screen.findByText(/Hello from AI/i)).toBeInTheDocument();
  });
});
