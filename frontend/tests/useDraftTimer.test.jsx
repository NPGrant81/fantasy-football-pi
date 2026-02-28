/* global vi */
import { render, act } from '@testing-library/react';
import React from 'react';
import { useDraftTimer } from '@hooks/useDraftTimer';

describe('useDraftTimer hook', () => {
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

  it('counts down and calls onTimeUp with true when it expires', () => {
    vi.useFakeTimers();
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
    act(() => vi.advanceTimersByTime(500));
    expect(timeUp).toHaveBeenCalledWith(true);

    vi.useRealTimers();
  });
});
