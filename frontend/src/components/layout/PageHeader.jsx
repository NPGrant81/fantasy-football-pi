import { pageHeader, pageSubtitle, pageTitle } from '@utils/uiStandards';

export default function PageHeader({
  title,
  subtitle,
  metadata,
  actions,
  className = '',
}) {
  return (
    <header className={`${pageHeader} ${className}`.trim()}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h1 className={pageTitle}>{title}</h1>
          {subtitle ? <p className={pageSubtitle}>{subtitle}</p> : null}
          {metadata ? (
            <div className="text-xs text-slate-500 dark:text-slate-400">{metadata}</div>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}
