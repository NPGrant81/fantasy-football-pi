// frontend/src/components/GlobalSearch.jsx
import React, { useState } from 'react';
import { FiSearch, FiUser, FiX } from 'react-icons/fi';

export default function GlobalSearch({ onPlayerSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);

  const handleSearch = async (val) => {
    setQuery(val);
    if (val.length < 2) return setResults([]);
    
    // In test mode, this pings your existing player endpoint
    try {
      const response = await fetch(`http://localhost:8000/players/search?q=${val}`);
      const data = await response.json();
      setResults(data);
    } catch (err) {
      console.error("Global Search Failed", err);
    }
  };

  return (
    <div className="relative w-full max-w-md group">
      <div className="flex items-center bg-slate-800 border border-slate-700 rounded-full px-4 py-2 focus-within:border-purple-500 transition-all">
        <FiSearch className="text-slate-400 mr-2" />
        <input 
          type="text"
          className="bg-transparent border-none outline-none text-white w-full text-sm"
          placeholder="Search Players (Cmd + K)"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
        />
        {query && <FiX className="cursor-pointer" onClick={() => setQuery('')} />}
      </div>

      {/* RESULTS DROPDOWN */}
      {results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden z-50">
          {results.map(player => (
            <div 
              key={player.id} 
              onClick={() => onPlayerSelect(player)}
              className="flex items-center gap-3 p-3 hover:bg-slate-800 cursor-pointer transition-colors border-b border-slate-800 last:border-0"
            >
              <div className="bg-slate-700 p-2 rounded-lg">
                <FiUser className="text-purple-400" />
              </div>
              <div>
                <div className="text-white font-bold text-sm">{player.name}</div>
                <div className="text-slate-500 text-xs">{player.position} - {player.nfl_team}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
