/* ignore-breakpoints */

import { pageShell } from '@utils/uiStandards';
import PageHeader from './PageHeader';

export default function PageTemplate({
  title,
  subtitle,
  metadata,
  actions,
  children,
  className = '',
  hideHeader = false,
}) {
  return (
    <div className={`${pageShell} ${className}`.trim()}>
      {!hideHeader ? (
        <PageHeader
          title={title}
          subtitle={subtitle}
          metadata={metadata}
          actions={actions}
        />
      ) : null}
      {children}
    </div>
  );
}
