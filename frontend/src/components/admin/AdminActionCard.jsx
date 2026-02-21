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
  accent = {
    hoverBorder: 'hover:border-blue-500/30',
    icon: 'text-blue-400',
    badge: 'bg-blue-900/30 text-blue-400',
    button: 'bg-blue-600 hover:bg-blue-500 text-white',
  },
}) {
  const IconComponent = icon;
  const buttonClass = disabled
    ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
    : accent.button;

  return (
    <div
      className={`bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl transition ${accent.hoverBorder}`}
    >
      <div className="flex justify-between items-start mb-4">
        <IconComponent className={`text-3xl ${accent.icon}`} />
        <div className={`text-xs font-bold px-2 py-1 rounded ${accent.badge}`}>
          {badge}
        </div>
      </div>
      <h3 className="text-xl font-bold mb-2">{title}</h3>
      <p className="text-slate-400 text-sm mb-6 min-h-[40px]">{description}</p>
      <button
        onClick={onClick}
        disabled={disabled}
        className={`w-full py-3 rounded-xl font-black uppercase flex items-center justify-center gap-2 transition ${buttonClass}`}
      >
        <IconComponent className={iconSpinsOnLoading && loading ? 'animate-spin' : ''} />
        {loading ? loadingLabel : actionLabel}
      </button>
    </div>
  );
}
