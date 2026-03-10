import React from 'react';
import { FiTool } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import PageTemplate from '@components/layout/PageTemplate';
import {
  buttonPrimary,
  cardSurface,
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
    <PageTemplate
      title="Commissioner Controls"
      subtitle="League-level management and configuration."
      metadata={
        <span className="inline-flex items-center gap-2">
          <FiTool className="text-cyan-500" />
          Admin tools
        </span>
      }
    >
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
    </PageTemplate>
  );
}
