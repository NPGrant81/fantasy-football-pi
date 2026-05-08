import { useState, useRef, useEffect, useCallback } from 'react';

// --- 1.1 CONFIGURATION ---
export function useDraftTimer(initialTime = 5, onTimeUp) {
  const [timeLeft, setTimeLeft] = useState(initialTime);
  const [isActive, setIsActive] = useState(false);
  const timerRef = useRef(null);
  // Guard: prevents double-fire if the effect runs twice or the timer ticks past 0
  const firedRef = useRef(false);

  // 1.1.1 Keep onTimeUp in a ref so the interval never needs to restart when the
  //        parent re-renders (e.g. handleDraft changes deps mid-countdown).
  const onTimeUpRef = useRef(onTimeUp);
  useEffect(() => {
    onTimeUpRef.current = onTimeUp;
  }, [onTimeUp]);

  // --- 1.2 ACTIONS ---
  const reset = useCallback(() => {
    firedRef.current = false;
    setIsActive(false);
    setTimeLeft(initialTime);
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, [initialTime]);

  // start() always resets the counter so subsequent auctions get a fresh countdown.
  const start = useCallback(() => {
    firedRef.current = false;
    setTimeLeft(initialTime);
    setIsActive(true);
  }, [initialTime]);

  // --- 1.3 THE HEARTBEAT: only ticks; no side-effects inside the updater ---
  useEffect(() => {
    if (!isActive) return;

    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isActive]);

  // --- 1.4 EXPIRY WATCHER: fires callback when timeLeft reaches 0 ---
  useEffect(() => {
    if (timeLeft !== 0 || !isActive || firedRef.current) return;

    firedRef.current = true;
    // Stop the interval and mark inactive
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    const deactivate = setTimeout(() => {
      setIsActive(false);
    }, 0);

    // Small grace period so any in-flight bid state settles before auto-draft fires
    const t = setTimeout(() => {
      if (onTimeUpRef.current) onTimeUpRef.current();
    }, 300);

    return () => {
      clearTimeout(deactivate);
      clearTimeout(t);
    };
  }, [timeLeft, isActive]);

  return { timeLeft, start, reset, isActive };
}
