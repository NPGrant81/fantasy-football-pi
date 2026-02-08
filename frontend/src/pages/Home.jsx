import { FiAward, FiActivity } from 'react-icons/fi' // <--- CHANGED HERE

export default function Home({ username }) {
  return (
    <div className="space-y-6 animate-fade-in">
      
      {/* 1. Welcome Banner */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6 shadow-lg">
        <h1 className="text-3xl font-black text-white italic tracking-tighter">LEAGUE DASHBOARD</h1>
        <p className="text-slate-400 mt-1">
          Welcome back, <span className="text-white font-bold">{username}</span>. 
          Open the menu <span className="inline-block bg-slate-700 px-2 py-0.5 rounded text-xs text-yellow-400">☰</span> to access the War Room.
        </p>
      </div>

      {/* 2. Standings & Activity Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* STANDINGS */}
        <div className="lg:col-span-2 bg-slate-900/50 border border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <FiAward className="text-yellow-500" size={24} /> {/* <--- CHANGED HERE */}
            <h2 className="text-lg font-bold text-white uppercase tracking-widest">Current Standings</h2>
          </div>
          
          {/* Mock Standings Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left text-slate-400">
              <thead className="text-xs text-slate-500 uppercase bg-slate-950/50">
                <tr>
                  <th className="px-4 py-3">Rank</th>
                  <th className="px-4 py-3">Team</th>
                  <th className="px-4 py-3">W-L</th>
                  <th className="px-4 py-3">PF</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-slate-800 hover:bg-slate-800/50">
                  <td className="px-4 py-3 font-bold text-yellow-500">1</td>
                  <td className="px-4 py-3 font-medium text-white">Team Crossland</td>
                  <td className="px-4 py-3">0-0</td>
                  <td className="px-4 py-3">0.00</td>
                </tr>
                <tr className="border-b border-slate-800 hover:bg-slate-800/50">
                  <td className="px-4 py-3 font-bold text-slate-400">2</td>
                  <td className="px-4 py-3 font-medium text-white">Team Grant</td>
                  <td className="px-4 py-3">0-0</td>
                  <td className="px-4 py-3">0.00</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* RECENT ACTIVITY */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <FiActivity className="text-blue-500" size={24} />
            <h2 className="text-lg font-bold text-white uppercase tracking-widest">League News</h2>
          </div>
          <div className="space-y-4">
            <div className="text-sm border-l-2 border-green-500 pl-3">
              <div className="text-slate-300 font-bold">New League Created</div>
              <div className="text-slate-500 text-xs">Today at 9:00 AM</div>
            </div>
            <div className="text-sm border-l-2 border-yellow-500 pl-3">
              <div className="text-slate-300 font-bold">Draft Scheduled</div>
              <div className="text-slate-500 text-xs">Tuesday at 8:00 PM</div>
            </div>
            <div className="text-center text-xs text-slate-600 mt-4 italic">End of feed</div>
          </div>
        </div>

      </div>
    </div>
  )
}