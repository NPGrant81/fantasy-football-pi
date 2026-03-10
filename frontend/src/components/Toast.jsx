// frontend/src/components/Toast.jsx
import React, { useEffect } from 'react';
import {
  FiAlertCircle,
  FiAlertTriangle,
  FiCheckCircle,
  FiInfo,
  FiLoader,
  FiX,
} from 'react-icons/fi';
import { layerToast } from '@utils/uiStandards';

export default function Toast({
  message,
  type = 'success',
  onClose,
  durationMs,
  sticky,
}) {
  const isSticky = sticky ?? type === 'loading';
  const defaultDurationMs =
    type === 'success' ? 4000 : type === 'info' ? 4500 : 5000;
  const resolvedDurationMs = durationMs ?? defaultDurationMs;
  const shouldAutoDismiss = !isSticky;

  // --- 1.1 AUTO DISMISS POLICY ---
  useEffect(() => {
    if (!shouldAutoDismiss) {
      return undefined;
    }
    const timer = setTimeout(() => {
      onClose();
    }, resolvedDurationMs);
    return () => clearTimeout(timer);
  }, [onClose, resolvedDurationMs, shouldAutoDismiss]);

  // --- 1.2 ESCAPE DISMISS SUPPORT ---
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  // --- 2.1 TYPE CONTRACT ---
  const styles = {
    success: 'bg-green-600/90 border-green-400 text-white',
    error: 'bg-red-600/90 border-red-400 text-white',
    warning: 'bg-amber-500/95 border-amber-300 text-slate-950',
    info: 'bg-blue-600/90 border-blue-400 text-white',
    loading: 'bg-slate-800/95 border-slate-500 text-white',
  };

  const icons = {
    success: <FiCheckCircle className="text-xl" />,
    error: <FiAlertCircle className="text-xl" />,
    warning: <FiAlertTriangle className="text-xl" />,
    info: <FiInfo className="text-xl" />,
    loading: <FiLoader className="text-xl animate-spin" />,
  };

  const ariaLive = type === 'error' ? 'assertive' : 'polite';
  const normalizedType = Object.prototype.hasOwnProperty.call(styles, type)
    ? type
    : 'info';

  return (
    <div
      className={`fixed top-10 md:top-12 left-1/2 -translate-x-1/2 ${layerToast} w-full sm:max-w-md px-4`}
      role="status"
      aria-live={ariaLive}
    >
      <div
        className={`
        relative overflow-hidden flex items-center justify-between px-6 py-4 
        rounded-2xl shadow-2xl border backdrop-blur-md 
        transition-all duration-300 transform
        ${styles[normalizedType]}
      `}
      >
        <div className="flex items-center gap-3">
          {icons[normalizedType]}
          <span className="font-bold tracking-tight">{message}</span>
        </div>

        <button
          onClick={onClose}
          className="ml-4 p-1 hover:bg-white/20 rounded-lg transition-colors"
          aria-label="Close notification"
        >
          <FiX className="text-lg" />
        </button>

        {shouldAutoDismiss && (
          <div
            className="absolute bottom-0 left-0 h-1 bg-white/40"
            style={{
              animation: `toast-progress ${resolvedDurationMs}ms linear forwards`,
            }}
          />
        )}
      </div>

      <style>{`
        @keyframes toast-progress {
          from { width: 100%; }
          to { width: 0%; }
        }
      `}</style>
    </div>
  );
}
