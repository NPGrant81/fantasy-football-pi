// src/hooks/useIdleTimer.js
//
// Tracks user inactivity and calls back at two thresholds:
//   onWarning()  — called `warningLeadSeconds` before timeout (show modal)
//   onTimeout()  — called when idle period expires (auto-logout)
//
// Usage:
//   const { resetTimer } = useIdleTimer({
//     idleMinutes:         30,   // from VITE_IDLE_TIMEOUT_MINUTES
//     warningLeadSeconds:  60,
//     onWarning:           () => setShowWarning(true),
//     onTimeout:           handleLogout,
//     enabled:             !!token,
//   });
//
// Call resetTimer() when the user clicks "Stay logged in" in the modal.

import { useCallback, useEffect, useRef } from 'react';

const ACTIVITY_EVENTS = [
  'mousemove',
  'mousedown',
  'keydown',
  'touchstart',
  'scroll',
  'wheel',
];

export function useIdleTimer({
  idleMinutes = 30,
  warningLeadSeconds = 60,
  onWarning,
  onTimeout,
  enabled = true,
}) {
  const warningTimerRef = useRef(null);
  const timeoutTimerRef = useRef(null);
  const onWarningRef = useRef(onWarning);
  const onTimeoutRef = useRef(onTimeout);
  // Track last reschedule time to throttle high-frequency activity events.
  const lastActivityRef = useRef(0);

  // Keep callback refs current without re-scheduling timers on every render.
  useEffect(() => { onWarningRef.current = onWarning; }, [onWarning]);
  useEffect(() => { onTimeoutRef.current = onTimeout; }, [onTimeout]);

  const clearTimers = useCallback(() => {
    if (warningTimerRef.current !== null) {
      clearTimeout(warningTimerRef.current);
      warningTimerRef.current = null;
    }
    if (timeoutTimerRef.current !== null) {
      clearTimeout(timeoutTimerRef.current);
      timeoutTimerRef.current = null;
    }
  }, []);

  const scheduleTimers = useCallback(() => {
    clearTimers();

    // Don't schedule if disabled or idle period is not a positive finite number.
    if (!Number.isFinite(idleMinutes) || idleMinutes <= 0) {
      return;
    }

    const idleMs        = idleMinutes * 60 * 1000;
    const warningMs     = idleMs - warningLeadSeconds * 1000;
    const warningDelay  = Math.max(warningMs, 0);

    if (warningDelay > 0) {
      warningTimerRef.current = setTimeout(() => {
        onWarningRef.current?.();
      }, warningDelay);
    } else {
      // Idle period is shorter than warning lead — fire warning immediately.
      onWarningRef.current?.();
    }

    timeoutTimerRef.current = setTimeout(() => {
      onTimeoutRef.current?.();
    }, idleMs);
  }, [idleMinutes, warningLeadSeconds, clearTimers]);

  const resetTimer = useCallback(() => {
    if (enabled) {
      scheduleTimers();
    }
  }, [enabled, scheduleTimers]);

  useEffect(() => {
    if (!enabled) {
      clearTimers();
      return;
    }

    scheduleTimers();

    // Throttle: only reschedule at most once per 500 ms to avoid timer churn
    // on high-frequency events like mousemove and scroll.
    const handleActivity = () => {
      const now = Date.now();
      if (now - lastActivityRef.current < 500) return;
      lastActivityRef.current = now;
      scheduleTimers();
    };

    ACTIVITY_EVENTS.forEach((event) => {
      window.addEventListener(event, handleActivity, { passive: true });
    });

    return () => {
      clearTimers();
      ACTIVITY_EVENTS.forEach((event) => {
        window.removeEventListener(event, handleActivity);
      });
    };
  }, [enabled, scheduleTimers, clearTimers]);

  return { resetTimer };
}
