import { useState, useRef, useEffect, useCallback } from 'react';

// --- 1.1 CONFIGURATION ---
export function useDraftTimer(initialTime = 10, onTimeUp) {
  const [timeLeft, setTimeLeft] = useState(initialTime);
  const [isActive, setIsActive] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false); // prevent race when clock hits zero
  const timerRef = useRef(null);

  // 1.1.1 Store onTimeUp in a Ref to prevent interval restarts
  // This is a "Pro" move to stop the timer from flickering if the parent re-renders
  const onTimeUpRef = useRef(onTimeUp);
  useEffect(() => {
    onTimeUpRef.current = onTimeUp;
  }, [onTimeUp]);

  // --- 1.2 THE ACTIONS (Stable Functions) ---
  const reset = useCallback(() => {
    setIsActive(false);
    setTimeLeft(initialTime);
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, [initialTime]);

  const start = useCallback(() => {
    setIsActive(true);
  }, []);

  // --- 1.3 THE HEARTBEAT (The Effect) ---
  useEffect(() => {
    // 1.3.1 Only start interval if active
    if (isActive) {
      timerRef.current = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            // 1.3.2 Logic for Expiration
            clearInterval(timerRef.current);
            timerRef.current = null;
            setIsActive(false);

            // if already processing, ignore
            if (!isProcessing) {
              setIsProcessing(true);
              // grace period before firing the callback; avoids race with "sold" event
              setTimeout(() => {
                if (onTimeUpRef.current) onTimeUpRef.current(true);
                setIsProcessing(false);
              }, 500);
            }

            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }

    // 1.3.3 Cleanup: Important to prevent memory leaks on the Pi
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isActive]); // Only depend on isActive to keep the timer steady

  return { timeLeft, start, reset, isActive };
}
