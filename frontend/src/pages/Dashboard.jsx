// frontend/src/pages/Dashboard.jsx
import React from 'react';

export default function Dashboard({ ownerId }) {
  void ownerId;

  // Commissioner dashboard is now dedicated to league management only.
  return (
    <div className="p-10 text-center text-slate-500 font-black uppercase">
      This page is now reserved for commissioner controls.
    </div>
  );
}
