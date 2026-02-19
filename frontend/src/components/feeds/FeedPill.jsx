export default function FeedPill({ children, className = '' }) {
  return (
    <span
      className={`inline-flex items-center bg-slate-900 border border-slate-800 rounded-full px-4 py-1 text-xs font-bold text-white shadow hover:border-yellow-400 transition-colors ${className}`}
    >
      {children}
    </span>
  );
}
