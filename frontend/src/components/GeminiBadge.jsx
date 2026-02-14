import React from 'react';

// Simple, self-contained badge component
// Note: We are using a simple <span> for the 'G' icon to avoid dependency errors 
// on the beach until you can run 'npm install react-icons'
const GeminiBadge = () => {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-blue-900/40 to-purple-900/40 rounded-full border border-white/10 shadow-lg backdrop-blur-sm w-fit mt-2">
      {/* Fallback Icon (Google 'G') */}
      <div className="w-4 h-4 rounded-full bg-white flex items-center justify-center">
        <span className="text-[10px] font-bold text-blue-600">G</span>
      </div>
      
      <span className="text-[10px] uppercase tracking-widest text-slate-300 font-semibold">
        Powered by <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">Gemini</span>
      </span>
    </div>
  );
};

export default GeminiBadge;
