/* ignore-breakpoints */
import React from 'react';
import { FiUsers } from 'react-icons/fi';
import {
  modalCloseButton,
  modalDescription,
  modalOverlay,
  modalPlaceholder,
  modalSurface,
  modalTitle,
} from '@utils/uiStandards';

export default function OwnerManagementModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className={modalOverlay}>
      <div className={modalSurface}>
        <button onClick={onClose} className={modalCloseButton}>
          ✕
        </button>
        <h2 className={modalTitle}>
          <FiUsers /> Invite/Manage Team Owners
        </h2>
        <p className={modalDescription}>
          Invite new owners, manage teams, and verify league access.
        </p>
        <div className={modalPlaceholder}>
          Owner management form coming soon...
        </div>
      </div>
    </div>
  );
}
