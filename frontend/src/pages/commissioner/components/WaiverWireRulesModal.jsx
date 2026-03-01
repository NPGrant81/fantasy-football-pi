/* ignore-breakpoints */
import React from 'react';
import { FiActivity } from 'react-icons/fi';
import {
  modalCloseButton,
  modalDescription,
  modalOverlay,
  modalPlaceholder,
  modalSurface,
  modalTitle,
} from '@utils/uiStandards';

export default function WaiverWireRulesModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className={modalOverlay}>
      <div className={modalSurface}>
        <button onClick={onClose} className={modalCloseButton}>
          ✕
        </button>
        <h2 className={modalTitle}>
          <FiActivity /> Set Waiver Wire Rules
        </h2>
        <p className={modalDescription}>
          Set rules for waiver claims, priorities, and deadlines.
        </p>
        <div className={modalPlaceholder}>
          Waiver wire rules form coming soon...
        </div>
      </div>
    </div>
  );
}
