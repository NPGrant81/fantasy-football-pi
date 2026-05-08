import React from 'react';

export default function ActionTile({
  icon: Icon,
  title,
  description,
  selected = false,
  disabled = false,
  onClick,
}) {
  const tone = selected
    ? 'border-cyan-500/70 bg-cyan-50 text-cyan-900 dark:border-cyan-500/70 dark:bg-cyan-900/20 dark:text-cyan-200'
    : 'border-slate-300 bg-white text-slate-900 hover:border-slate-400 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-200 dark:hover:border-slate-700';

  return (
    <button
      type="button"
      className={`min-h-[56px] md:min-h-[88px] rounded-xl border px-2 py-2 md:p-3 text-left transition disabled:cursor-not-allowed disabled:opacity-60 ${tone}`}
      onClick={onClick}
      disabled={disabled}
      aria-pressed={selected}
    >
      <span className="flex items-center gap-1.5 md:gap-2 text-[11px] md:text-xs font-black uppercase tracking-wider">
        {Icon ? <Icon aria-hidden="true" /> : null}
        {title}
      </span>
      <span className="mt-1 hidden md:block text-xs font-medium normal-case opacity-90">{description}</span>
    </button>
  );
}
