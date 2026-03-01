/* ignore-breakpoints: dashboard layout is fully managed by uiStandards page shell; responsive behaviour is not required at this level */
// frontend/src/pages/Dashboard.jsx
import React from 'react';
import {
  cardSurface,
  pageHeader,
  pageShell,
  pageTitle,
} from '@utils/uiStandards';

export default function Dashboard({ ownerId }) {
  void ownerId;

  // Commissioner dashboard is now dedicated to league management only.
  return (
    <div className={pageShell}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Dashboard</h1>
      </div>
      <div
        className={`${cardSurface} text-center text-slate-600 dark:text-slate-400 font-bold`}
      >
        This page is now reserved for commissioner controls.
      </div>
    </div>
  );
}
