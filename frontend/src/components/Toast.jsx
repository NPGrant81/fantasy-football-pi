// frontend/src/components/Toast.jsx
import React, { useEffect } from 'react';
import { bgColors, textColors, borderColors } from '../utils/uiHelpers';
import { FiCheckCircle, FiAlertCircle, FiInfo, FiX } from 'react-icons/fi';

export default function Toast({ message, type = 'success', onClose }) {
  // Auto-dismiss after 5 seconds (updated from 3s)
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, 5000);
    return () => clearTimeout(timer);
  }, [onClose]);

  // Merged Styles: Keeping your colors but adding transparency and centering
  const styles = {
    success: 'bg-green-600/90 border-green-400 text-white',
    error: 'bg-red-600/90 border-red-400 text-white',
    info: 'bg-blue-600/90 border-blue-400 text-white',
  };

  const icons = {
    success: <FiCheckCircle className="text-xl" />,
    error: <FiAlertCircle className="text-xl" />,
    info: <FiInfo className="text-xl" />,
  };

  return (
    // Positioned Top-Center with a slide-in animation
    <div className="fixed top-10 left-1/2 -translate-x-1/2 z-[9999] w-full max-w-md px-4">
      <div
        className={`
        relative overflow-hidden flex items-center justify-between px-6 py-4 
        rounded-2xl shadow-2xl border backdrop-blur-md 
        transition-all duration-300 transform
        ${styles[type]}
      `}
      >
        <div className="flex items-center gap-3">
          {icons[type]}
          <span className="font-bold tracking-tight">{message}</span>
        </div>

        {/* Manual Close Prompt */}
        <button
          onClick={onClose}
          className="ml-4 p-1 hover:bg-white/20 rounded-lg transition-colors"
          aria-label="Close notification"
        >
          <FiX className="text-lg" />
        </button>

        {/* The 5-Second Progress Bar */}
        <div
          className="absolute bottom-0 left-0 h-1 bg-white/40"
          style={{
            animation: 'toast-progress 5000ms linear forwards',
          }}
        />
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
