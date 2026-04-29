// frontend/tests/useIdleTimer.test.js
// Tests for the useIdleTimer hook.

import { renderHook, act } from '@testing-library/react';
import { useIdleTimer } from '../src/hooks/useIdleTimer';

describe('useIdleTimer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('calls onWarning before onTimeout', () => {
    const onWarning = vi.fn();
    const onTimeout = vi.fn();

    renderHook(() =>
      useIdleTimer({
        idleMinutes:        1,   // 60 000 ms
        warningLeadSeconds: 10,  // warning at 50 000 ms
        onWarning,
        onTimeout,
        enabled: true,
      })
    );

    // Neither fired yet
    expect(onWarning).not.toHaveBeenCalled();
    expect(onTimeout).not.toHaveBeenCalled();

    // Advance to just before warning
    act(() => { vi.advanceTimersByTime(49_999); });
    expect(onWarning).not.toHaveBeenCalled();

    // Advance past warning threshold
    act(() => { vi.advanceTimersByTime(1); });
    expect(onWarning).toHaveBeenCalledTimes(1);
    expect(onTimeout).not.toHaveBeenCalled();

    // Advance past timeout
    act(() => { vi.advanceTimersByTime(10_000); });
    expect(onTimeout).toHaveBeenCalledTimes(1);
  });

  test('does not fire when disabled', () => {
    const onWarning = vi.fn();
    const onTimeout = vi.fn();

    renderHook(() =>
      useIdleTimer({
        idleMinutes:        1,
        warningLeadSeconds: 10,
        onWarning,
        onTimeout,
        enabled: false,
      })
    );

    act(() => { vi.advanceTimersByTime(120_000); });
    expect(onWarning).not.toHaveBeenCalled();
    expect(onTimeout).not.toHaveBeenCalled();
  });

  test('resetTimer restarts the countdown', () => {
    const onWarning = vi.fn();
    const onTimeout = vi.fn();

    const { result } = renderHook(() =>
      useIdleTimer({
        idleMinutes:        1,   // 60 000 ms
        warningLeadSeconds: 10,  // warning at 50 000 ms
        onWarning,
        onTimeout,
        enabled: true,
      })
    );

    // Advance close to warning threshold
    act(() => { vi.advanceTimersByTime(49_000); });
    expect(onWarning).not.toHaveBeenCalled();

    // Reset — should push warning back by another 50 000 ms
    act(() => { result.current.resetTimer(); });

    // Advance another 49 000 ms (total 98 000 ms from start, 49 000 from reset)
    act(() => { vi.advanceTimersByTime(49_000); });
    expect(onWarning).not.toHaveBeenCalled();

    // Cross the warning threshold from reset point
    act(() => { vi.advanceTimersByTime(1_000); });
    expect(onWarning).toHaveBeenCalledTimes(1);
  });

  test('clears timers when enabled toggles from true to false', () => {
    const onWarning = vi.fn();
    const onTimeout = vi.fn();

    const { rerender } = renderHook(
      ({ enabled }) =>
        useIdleTimer({
          idleMinutes:        1,
          warningLeadSeconds: 10,
          onWarning,
          onTimeout,
          enabled,
        }),
      { initialProps: { enabled: true } }
    );

    // Disable before any timer fires
    act(() => { rerender({ enabled: false }); });

    // Advance past timeout — should not fire
    act(() => { vi.advanceTimersByTime(120_000); });
    expect(onWarning).not.toHaveBeenCalled();
    expect(onTimeout).not.toHaveBeenCalled();
  });

  test('activity event resets the countdown', () => {
    const onWarning = vi.fn();
    const onTimeout = vi.fn();

    renderHook(() =>
      useIdleTimer({
        idleMinutes:        1,
        warningLeadSeconds: 10,
        onWarning,
        onTimeout,
        enabled: true,
      })
    );

    // Advance to 49 s
    act(() => { vi.advanceTimersByTime(49_000); });
    expect(onWarning).not.toHaveBeenCalled();

    // Simulate user activity
    act(() => { window.dispatchEvent(new MouseEvent('mousemove')); });

    // Advance another 49 s from now — still should not hit warning
    act(() => { vi.advanceTimersByTime(49_000); });
    expect(onWarning).not.toHaveBeenCalled();
  });
});
