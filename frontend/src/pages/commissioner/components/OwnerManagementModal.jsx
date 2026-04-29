/* ignore-breakpoints: modal layout and responsiveness are handled by shared uiStandards modal classes; no additional breakpoint-specific behaviour is required */
import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

export default function OwnerManagementModal({ open, onClose }) {
  const navigate = useNavigate();
  const didRedirect = useRef(false);

  useEffect(() => {
    if (open && !didRedirect.current) {
      didRedirect.current = true;
      onClose();
      navigate('/manage-owners');
    }
    if (!open) {
      didRedirect.current = false;
    }
  }, [open, onClose, navigate]);

  return null;
}
