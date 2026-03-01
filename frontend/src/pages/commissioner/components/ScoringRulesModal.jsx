import React from 'react';
import { FiSettings } from 'react-icons/fi';
import {
  modalCloseButton,
  modalDescription,
  modalOverlay,
  modalPlaceholder,
  modalSurface,
  modalTitle,
} from '@utils/uiStandards';

export default function ScoringRulesModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className={modalOverlay}>
      <div className={modalSurface}>
        <button onClick={onClose} className={modalCloseButton}>
          ✕
        </button>
        <h2 className={modalTitle}>
          <FiSettings /> Set Scoring Rules
        </h2>
        <p className={modalDescription}>
          Configure how points are awarded for all league actions.
        </p>
        <div className={modalPlaceholder}>
          Scoring rules form coming soon...
        </div>
      </div>
    </div>
  );
}
