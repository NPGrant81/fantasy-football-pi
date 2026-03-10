/* ignore-breakpoints: locker room is a fixed demo/admin page where responsive layout is not required */
import React from 'react';
import PageTemplate from '@components/layout/PageTemplate';
import {
  cardSurface,
} from '@utils/uiStandards';

export default function LockerRoom() {
  return (
    <PageTemplate title="Locker Room" subtitle="Draft-day collaboration area.">
      <div
        className={`${cardSurface} text-slate-600 dark:text-slate-400 font-medium`}
      >
        Locker room demo page (logic removed).
      </div>
    </PageTemplate>
  );
}
