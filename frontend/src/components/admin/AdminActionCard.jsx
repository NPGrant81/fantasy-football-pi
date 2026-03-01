/* ignore-breakpoints */
import {
  adminActionToneStyles,
  buttonSecondary,
  cardSurface,
} from '@utils/uiStandards';

export default function AdminActionCard({
  icon,
  badge,
  title,
  description,
  onClick,
  disabled = false,
  loading = false,
  loadingLabel,
  actionLabel,
  iconSpinsOnLoading = false,
  tone = 'blue',
}) {
  const IconComponent = icon;
  const toneStyle = adminActionToneStyles[tone] || adminActionToneStyles.blue;
  const buttonClass = disabled
    ? `${buttonSecondary} opacity-50 cursor-not-allowed`
    : toneStyle.button;

  return (
    <div className={`${cardSurface} transition ${toneStyle.hoverBorder}`}>
      <div className="flex justify-between items-start mb-4">
        <IconComponent className={`text-3xl ${toneStyle.icon}`} />
        <div
          className={`text-xs font-bold px-2 py-1 rounded ${toneStyle.badge}`}
        >
          {badge}
        </div>
      </div>
      <h3 className="text-xl font-bold mb-2 text-slate-900 dark:text-white">
        {title}
      </h3>
      <p className="text-slate-600 dark:text-slate-400 text-sm mb-6 min-h-[40px]">
        {description}
      </p>
      <button
        onClick={onClick}
        disabled={disabled}
        className={`w-full py-3 rounded-xl font-black uppercase flex items-center justify-center gap-2 transition ${buttonClass}`}
      >
        <IconComponent
          className={iconSpinsOnLoading && loading ? 'animate-spin' : ''}
        />
        {loading ? loadingLabel : actionLabel}
      </button>
    </div>
  );
}
