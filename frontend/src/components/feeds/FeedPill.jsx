/* ignore-breakpoints */
export default function FeedPill({ children, className = '' }) {
  return (
    <span
      className={`inline-flex items-center bg-slate-100 border border-slate-300 text-slate-700 rounded-full px-4 py-1 text-xs font-bold shadow hover:border-yellow-400 transition-colors dark:bg-slate-900 dark:border-slate-800 dark:text-white ${className}`}
    >
      {children}
    </span>
  );
}
