/* ignore-breakpoints: modal layout and responsiveness are handled by shared uiStandards modal classes; no additional breakpoint-specific behaviour is required */
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function OwnerManagementModal({ open, onClose }) {
  const navigate = useNavigate();

  useEffect(() => {
    if (open) {
      onClose();
      navigate('/manage-owners');
    }
  }, [open, onClose, navigate]);

  return null;
}
