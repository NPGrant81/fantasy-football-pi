import { FiAlertTriangle, FiInfo, FiLoader } from 'react-icons/fi';
import { textMuted } from '@utils/uiStandards';

export function LoadingState({ message = 'Loading...', className = '' }) {
  return (
    <div
      className={`inline-flex items-center gap-2 ${textMuted} ${className}`.trim()}
      role="status"
      aria-live="polite"
    >
      <FiLoader className="animate-spin" />
      <span>{message}</span>
    </div>
  );
}

export function EmptyState({ message = 'No data available.', className = '' }) {
  return (
    <div className={`${textMuted} ${className}`.trim()}>
      <div className="inline-flex items-center gap-2">
        <FiInfo />
        <span>{message}</span>
      </div>
    </div>
  );
}

export function ErrorState({ message = 'Something went wrong.', className = '' }) {
  return (
    <div
      className={`inline-flex items-center gap-2 text-sm text-red-400 ${className}`.trim()}
      role="alert"
      aria-live="assertive"
    >
      <FiAlertTriangle />
      <span>{message}</span>
    </div>
  );
}
