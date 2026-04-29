// frontend/tests/IdleWarningModal.test.jsx
// Tests for the IdleWarningModal component.

import { render, screen, fireEvent, act } from '@testing-library/react';
import IdleWarningModal from '../src/components/IdleWarningModal';

describe('IdleWarningModal', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('renders nothing when isOpen is false', () => {
    const { container } = render(
      <IdleWarningModal
        isOpen={false}
        secondsRemaining={60}
        onStay={vi.fn()}
        onLogout={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders warning text and countdown when open', () => {
    render(
      <IdleWarningModal
        isOpen={true}
        secondsRemaining={60}
        onStay={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Session Timeout Warning')).toBeInTheDocument();
    expect(screen.getByText('60s')).toBeInTheDocument();
  });

  test('countdown decrements each second', () => {
    render(
      <IdleWarningModal
        isOpen={true}
        secondsRemaining={5}
        onStay={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    expect(screen.getByText('5s')).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByText('4s')).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByText('3s')).toBeInTheDocument();
  });

  test('calls onStay when Stay Logged In button clicked', () => {
    const onStay = vi.fn();

    render(
      <IdleWarningModal
        isOpen={true}
        secondsRemaining={60}
        onStay={onStay}
        onLogout={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /stay logged in/i }));
    expect(onStay).toHaveBeenCalledTimes(1);
  });

  test('calls onLogout when Log Out Now button clicked', () => {
    const onLogout = vi.fn();

    render(
      <IdleWarningModal
        isOpen={true}
        secondsRemaining={60}
        onStay={vi.fn()}
        onLogout={onLogout}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /log out now/i }));
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  test('stops countdown and clears interval when closed', () => {
    const { rerender } = render(
      <IdleWarningModal
        isOpen={true}
        secondsRemaining={5}
        onStay={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    act(() => { vi.advanceTimersByTime(2000); });
    expect(screen.getByText('3s')).toBeInTheDocument();

    // Close modal — should render nothing and stop ticker
    rerender(
      <IdleWarningModal
        isOpen={false}
        secondsRemaining={5}
        onStay={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    // Advancing time after close should not throw
    act(() => { vi.advanceTimersByTime(5000); });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  test('resets countdown when reopened with new secondsRemaining', () => {
    const { rerender } = render(
      <IdleWarningModal
        isOpen={true}
        secondsRemaining={10}
        onStay={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    act(() => { vi.advanceTimersByTime(3000); });
    expect(screen.getByText('7s')).toBeInTheDocument();

    // Close then reopen with fresh count
    rerender(
      <IdleWarningModal
        isOpen={false}
        secondsRemaining={60}
        onStay={vi.fn()}
        onLogout={vi.fn()}
      />
    );
    rerender(
      <IdleWarningModal
        isOpen={true}
        secondsRemaining={60}
        onStay={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    expect(screen.getByText('60s')).toBeInTheDocument();
  });
});
