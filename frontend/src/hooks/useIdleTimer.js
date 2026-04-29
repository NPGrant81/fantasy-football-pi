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

    const handleActivity = () => {
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
