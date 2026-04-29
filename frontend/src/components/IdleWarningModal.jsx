// src/components/IdleWarningModal.jsx
//
// Shown `warningLeadSeconds` before auto-logout fires.
// Displays a live countdown; user can stay or log out early.

import React, { useEffect, useRef, useState } from 'react';
import {
  buttonDanger,
  buttonSecondary,
  modalDescription,
  modalOverlay,
  modalSurface,
  modalTitle,
} from '@utils/uiStandards';

export default function IdleWarningModal({
  isOpen,
  secondsRemaining: initialSeconds,
  onStay,
  onLogout,
}) {
  const [seconds, setSeconds] = useState(initialSeconds);
  const intervalRef = useRef(null);

  // Sync seconds to initialSeconds whenever the prop changes (e.g. if the
  // caller passes a live remaining-time value instead of a fixed constant).
  useEffect(() => {
    setSeconds(initialSeconds);
  }, [initialSeconds]);

  // Reset and start countdown whenever the modal opens.
  useEffect(() => {
    if (!isOpen) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Ensure countdown starts fresh from the current initialSeconds value.
    setSeconds(initialSeconds);

    intervalRef.current = setInterval(() => {
      setSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isOpen, initialSeconds]);

  if (!isOpen) return null;

  return (
    <div className={modalOverlay} role="dialog" aria-modal="true" aria-labelledby="idle-modal-title">
      <div className={`${modalSurface} sm:max-w-md`}>
        <h2 id="idle-modal-title" className={modalTitle}>
          {/* Warning icon */}
          <svg
            className="h-6 w-6 text-yellow-500 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
            />
          </svg>
          Session Timeout Warning
        </h2>

        <p className={modalDescription}>
          You have been inactive for a while. You will be automatically logged out in:
        </p>

        <div
          className="mb-6 text-center text-5xl font-bold tabular-nums text-cyan-500 dark:text-cyan-400"
          aria-live="polite"
          aria-label={`${seconds} seconds remaining`}
        >
          {seconds}s
        </div>

        <p className={`${modalDescription} mb-6`}>
          Click <strong>Stay Logged In</strong> to continue your session, or{' '}
          <strong>Log Out Now</strong> to sign out immediately.
        </p>

        <div className="flex gap-3 justify-end">
          <button
            type="button"
            className={buttonDanger}
            onClick={onLogout}
          >
            Log Out Now
          </button>
          <button
            type="button"
            className={buttonSecondary}
            onClick={onStay}
            autoFocus
          >
            Stay Logged In
          </button>
        </div>
      </div>
    </div>
  );
}
