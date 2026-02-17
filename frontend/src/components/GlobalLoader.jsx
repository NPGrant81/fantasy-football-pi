// frontend/src/components/GlobalLoader.jsx
import React from 'react';

export default function GlobalLoader() {
  return (
    <div className="flex flex-col items-center justify-center p-10 space-y-4">
      <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
      <p className="text-slate-400 font-medium animate-pulse">
        Fetching NFL Reality...
      </p>
    </div>
  );
}
