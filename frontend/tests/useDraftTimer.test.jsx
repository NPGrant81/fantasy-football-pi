import { vi } from 'vitest';
import { render, act } from '@testing-library/react';
import React from 'react';
import { useDraftTimer } from '@hooks/useDraftTimer';

describe('useDraftTimer hook', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());
  function TimerTest({ initial, onTimeUp }) {
    const { timeLeft, start, reset, isActive } = useDraftTimer(
      initial,
      onTimeUp
    );
    return (
      <div>
        <span data-testid="time">{timeLeft}</span>
        <span data-testid="active">{isActive ? 'yes' : 'no'}</span>
        <button onClick={start}>start</button>
        <button onClick={reset}>reset</button>
      </div>
    );
  }

  it('counts down and calls onTimeUp once after the grace period', () => {
    const timeUp = vi.fn();
    const { getByText, getByTestId } = render(
      <TimerTest initial={3} onTimeUp={timeUp} />
    );

    act(() => {
      getByText('start').click();
    });

    expect(getByTestId('time').textContent).toBe('3');
    expect(getByTestId('active').textContent).toBe('yes');

    // advance until expiration
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(getByTestId('time').textContent).toBe('0');
    expect(timeUp).not.toHaveBeenCalled();

    // grace period should fire the callback
    act(() => vi.advanceTimersByTime(299));
    expect(timeUp).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(timeUp).toHaveBeenCalledExactlyOnceWith();
    expect(getByTestId('active').textContent).toBe('no');
    act(() => vi.advanceTimersByTime(5000));
    expect(timeUp).toHaveBeenCalledTimes(1);
  });

  it('cancels pending expiry when reset during the grace period', () => {
    const timeUp = vi.fn();
    const { getByText, getByTestId } = render(
      <TimerTest initial={1} onTimeUp={timeUp} />
    );
    act(() => getByText('start').click());
    act(() => vi.advanceTimersByTime(1000));
    act(() => getByText('reset').click());
    act(() => vi.advanceTimersByTime(300));
    expect(timeUp).not.toHaveBeenCalled();
    expect(getByTestId('time').textContent).toBe('1');
    expect(getByTestId('active').textContent).toBe('no');
  });

  it('cancels pending expiry on unmount', () => {
    const timeUp = vi.fn();
    const { getByText, unmount } = render(
      <TimerTest initial={1} onTimeUp={timeUp} />
    );
    act(() => getByText('start').click());
    act(() => vi.advanceTimersByTime(1000));
    unmount();
    act(() => vi.advanceTimersByTime(300));
    expect(timeUp).not.toHaveBeenCalled();
  });
});
