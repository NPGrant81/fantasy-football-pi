export const pageShell = 'w-full p-4 md:p-6 space-y-6';

export const layoutAlertBar =
  'h-10 bg-slate-200 dark:bg-slate-800 text-xs text-yellow-800 dark:text-yellow-300 flex items-center px-6';

export const pageHeader =
  'space-y-1 border-b border-slate-300 dark:border-slate-800 pb-4';

export const pageTitle =
  'text-2xl md:text-3xl font-black tracking-tight text-slate-900 dark:text-white';

export const pageSubtitle = 'text-sm text-slate-600 dark:text-slate-400';

export const cardSurface =
  'rounded-xl border border-slate-300 dark:border-slate-800 bg-white/80 dark:bg-slate-900/50 p-4 md:p-6 shadow-sm';

export const tableSurface =
  'overflow-x-auto rounded-xl border border-slate-300 dark:border-slate-800 bg-white/80 dark:bg-slate-900/50';

export const tableHead =
  'bg-slate-100 dark:bg-slate-950/70 text-xs uppercase tracking-wider text-slate-600 dark:text-slate-500';

export const inputBase =
  'w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-cyan-500/40';

export const buttonBase =
  'inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-bold transition focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-slate-950';

export const buttonPrimary = `${buttonBase} bg-cyan-600 text-white hover:bg-cyan-500 focus:ring-cyan-500`;

export const buttonSecondary = `${buttonBase} bg-slate-200 text-slate-900 hover:bg-slate-300 dark:bg-slate-800 dark:text-white dark:hover:bg-slate-700 focus:ring-slate-500`;

export const buttonDanger = `${buttonBase} bg-red-600 text-white hover:bg-red-500 focus:ring-red-500`;

export const modalOverlay =
  'fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4';

export const modalSurface =
  'relative w-full sm:max-w-lg rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 shadow-2xl';

export const modalCloseButton =
  'absolute right-4 top-4 inline-flex items-center justify-center rounded-md border border-slate-300 dark:border-slate-700 px-2 py-1 text-sm font-bold text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white';

export const modalTitle =
  'mb-4 flex items-center gap-2 text-2xl font-bold text-slate-900 dark:text-white';

export const modalDescription =
  'mb-4 text-sm text-slate-600 dark:text-slate-400';

export const modalPlaceholder =
  'text-center text-slate-500 dark:text-slate-400';

export const adminActionToneStyles = {
  blue: {
    hoverBorder: 'hover:border-blue-500/30',
    icon: 'text-blue-400',
    badge: 'bg-blue-900/30 text-blue-400',
    button: 'bg-blue-600 hover:bg-blue-500 text-white',
  },
  green: {
    hoverBorder: 'hover:border-green-500/30',
    icon: 'text-green-400',
    badge: 'bg-green-900/30 text-green-400',
    button: 'bg-green-600 hover:bg-green-500 text-white',
  },
  yellow: {
    hoverBorder: 'hover:border-yellow-500/30',
    icon: 'text-yellow-400',
    badge: 'bg-yellow-900/30 text-yellow-400',
    button: 'bg-yellow-600 hover:bg-yellow-500 text-white',
  },
  red: {
    hoverBorder: 'hover:border-red-500/30',
    icon: 'text-red-400',
    badge: 'bg-red-900/30 text-red-400',
    button: 'bg-red-600 hover:bg-red-500 text-white',
  },
  purple: {
    hoverBorder: 'hover:border-purple-500/30',
    icon: 'text-purple-400',
    badge: 'bg-purple-900/30 text-purple-400',
    button: 'bg-purple-600 hover:bg-purple-500 text-white',
  },
  indigo: {
    hoverBorder: 'hover:border-indigo-500/30',
    icon: 'text-indigo-400',
    badge: 'bg-indigo-900/30 text-indigo-400',
    button: 'bg-indigo-600 hover:bg-indigo-500 text-white',
  },
};
