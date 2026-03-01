/* ignore-breakpoints: this modal's layout and responsiveness are handled by shared uiStandards modal classes; no additional breakpoint-specific behaviour is required */
import React from 'react';
import { FiShield } from 'react-icons/fi';
import {
  modalCloseButton,
  modalDescription,
  modalOverlay,
  modalPlaceholder,
  modalSurface,
  modalTitle,
} from '@utils/uiStandards';

export default function TradeRulesModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className={modalOverlay}>
      <div className={modalSurface}>
        <button onClick={onClose} className={modalCloseButton}>
          ✕
        </button>
        <h2 className={modalTitle}>
          <FiShield /> Set Trade Rules
        </h2>
        <p className={modalDescription}>
          Configure trade review, veto, and deadlines.
        </p>
        <div className={modalPlaceholder}>Trade rules form coming soon...</div>
      </div>
    </div>
  );
}
