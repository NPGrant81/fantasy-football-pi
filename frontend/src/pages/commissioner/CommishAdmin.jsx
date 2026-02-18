import React from 'react';
import { FiTool } from 'react-icons/fi';

export default function CommishAdmin() {
  const navigate = (path) => {
    window.location.href = path;
  };
  return (
    <div className="p-8 max-w-6xl mx-auto text-white min-h-screen">
      <div className="flex items-center gap-4 mb-10 border-b border-slate-700 pb-6">
        <FiTool className="text-4xl text-purple-500" />
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Commissioner Controls
          </h1>
          <p className="text-slate-400 text-sm">
            League-level management and configuration
          </p>
        </div>
      </div>
      <div className="w-full flex flex-wrap justify-center gap-8 mb-12">
        <button
          className="bg-slate-900 border-2 border-green-500 text-green-400 rounded-2xl px-10 py-10 text-2xl font-black shadow-xl hover:bg-green-900/40 transition min-w-[260px] min-h-[160px]"
          onClick={() => navigate('/manage-users')}
        >
          MANAGE<br />OWNERS
        </button>
        <button
          className="bg-slate-900 border-2 border-green-500 text-green-400 rounded-2xl px-10 py-10 text-2xl font-black shadow-xl hover:bg-green-900/40 transition min-w-[260px] min-h-[160px]"
          onClick={() => navigate('/commissioner/manage-scoring-rules')}
        >
          MANAGE<br />SCORING RULES
        </button>
        <button
          className="bg-slate-900 border-2 border-green-500 text-green-400 rounded-2xl px-10 py-10 text-2xl font-black shadow-xl hover:bg-green-900/40 transition min-w-[260px] min-h-[160px]"
          onClick={() => navigate('/commissioner/manage-waiver-rules')}
        >
          MANAGE<br />WAIVER RULES
        </button>
        <button
          className="bg-slate-900 border-2 border-green-500 text-green-400 rounded-2xl px-10 py-10 text-2xl font-black shadow-xl hover:bg-green-900/40 transition min-w-[260px] min-h-[160px]"
          onClick={() => navigate('/commissioner/manage-trades')}
        >
          MANAGE<br />TRADES
        </button>
      </div>
    </div>
  );
}
