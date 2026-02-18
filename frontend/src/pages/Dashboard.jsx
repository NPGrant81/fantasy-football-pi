// frontend/src/pages/Dashboard.jsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiTrendingUp, FiRepeat, FiBell, FiPlus, FiList } from 'react-icons/fi';

// Professional Imports
import apiClient from '@api/client';
import { getPosColor } from '../utils/uiHelpers';
import { normalizePos } from '../utils/draftHelpers';
import { ChatInterface } from '@components/chat';

export default function Dashboard({ ownerId }) {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    if (!ownerId) return;

    // Using the centralized client instead of hardcoded localhost
    apiClient
      .get(`/dashboard/${ownerId}`)
      .then((res) => setSummary(res.data))
      .catch((err) => console.error('Dashboard fetch failed', err));
  }, [ownerId]);

  // Commissioner dashboard is now dedicated to league management only.
  return (
    <div className="p-10 text-center text-slate-500 font-black uppercase">
      This page is now reserved for commissioner controls.
    </div>
  );
}
