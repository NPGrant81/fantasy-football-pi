// --- 1.0 COMPONENT DECLARATION ---
// This is a pure functional component for system-wide attribution.
export default function GeminiBadge() {
  return (
    <div className="flex items-center gap-2 px-3 py-1 bg-slate-950 border border-slate-800 rounded-full group cursor-default select-none hover:bg-slate-900 transition-colors duration-300">
      {/* 1.1 THE ANIMATED NEURAL CORE */}
      <div className="relative flex h-2.5 w-2.5">
        {/* Radar Pulse Effect */}
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-40"></span>

        {/* Multi-layered Gradient Core */}
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-gradient-to-tr from-blue-600 via-purple-500 to-pink-400 shadow-[0_0_8px_rgba(59,130,246,0.6)] group-hover:scale-110 transition-transform duration-300"></span>
      </div>

      {/* 1.2 THE BRANDING LOGIC */}
      <div className="flex items-center gap-1.5">
        {/* Muted label for compliance */}
        <span className="text-[9px] font-bold tracking-widest uppercase text-slate-500">
          Powered By
        </span>

        {/* High-visibility Brand Mark */}
        <span className="text-[10px] font-black tracking-[0.1em] uppercase italic text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 animate-gradient-x">
          Gemini AI
        </span>
      </div>
    </div>
  );
}
