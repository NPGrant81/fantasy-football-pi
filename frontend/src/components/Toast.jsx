// frontend/src/components/Toast.jsx
import React, { useEffect } from 'react';
import { FiCheckCircle, FiAlertCircle, FiInfo, FiX } from 'react-icons/fi';

export default function Toast({ message, type = 'success', onClose }) {
  // Auto-dismiss after 3 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  // Style configurations
  const styles = {
    success: 'bg-green-600 border-green-500 text-white',
    error: 'bg-red-600 border-red-500 text-white',
    info: 'bg-blue-600 border-blue-500 text-white',
  };

  const icons = {
    success: <FiCheckCircle className="text-xl" />,
    error: <FiAlertCircle className="text-xl" />,
    info: <FiInfo className="text-xl" />,
  };

  return (
    <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-6 py-4 rounded-xl shadow-2xl border ${styles[type]} animate-bounce-in`}>
      {icons[type]}
      <div className="font-bold">{message}</div>
      <button onClick={onClose} className="ml-4 opacity-70 hover:opacity-100">
        <FiX />
      </button>
    </div>
  );
}