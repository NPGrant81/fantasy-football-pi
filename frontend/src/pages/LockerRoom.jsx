/* ignore-breakpoints: locker room is a fixed demo/admin page where responsive layout is not required */
import React from 'react';
import {
  cardSurface,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '@utils/uiStandards';

export default function LockerRoom() {
  return (
    <div className={pageShell}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Locker Room</h1>
        <p className={pageSubtitle}>Draft-day collaboration area.</p>
      </div>
      <div
        className={`${cardSurface} text-slate-600 dark:text-slate-400 font-medium`}
      >
        Locker room demo page (logic removed).
      </div>
    </div>
  );
}
