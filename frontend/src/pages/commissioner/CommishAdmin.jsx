import React from 'react';
import { FiTool } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import {
  buttonPrimary,
  cardSurface,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '@utils/uiStandards';

/* ignore-breakpoints */

export default function CommishAdmin() {
  const navigate = useNavigate();

  const actions = [
    { label: 'Manage Owners', to: '/manage-users' },
    {
      label: 'Manage Scoring Rules',
      to: '/commissioner/manage-scoring-rules',
    },
    { label: 'Edit Waiver Rules', to: '/waiver-rules' },
    { label: 'Manage Trades', to: '/commissioner/manage-trades' },
  ];

  return (
    <div className={pageShell}>
      <div className={pageHeader}>
        <div className="flex items-center gap-3">
          <FiTool className="text-2xl text-cyan-500" />
          <h1 className={pageTitle}>Commissioner Controls</h1>
        </div>
        <p className={pageSubtitle}>
          League-level management and configuration.
        </p>
      </div>

      <div className={cardSurface}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {actions.map((action) => (
            <button
              key={action.to}
              type="button"
              className={`${buttonPrimary} w-full justify-start`}
              onClick={() => navigate(action.to)}
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
