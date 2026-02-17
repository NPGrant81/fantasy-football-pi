import React, { useState } from 'react';
import { FiX, FiInfo } from 'react-icons/fi';

const ClaimModal = ({ player, isOpen, onClose, onConfirm, userRoster = [] }) => {
  const [bid, setBid] = useState(1);
  const [playerToDrop, setPlayerToDrop] = useState("");

  if (!isOpen || !player) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    onConfirm({
      playerId: player.id,
      bidAmount: bid,
      dropPlayerId: playerToDrop
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-md shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-slate-800 bg-slate-800/50">
          <h3 className="text-xl font-bold text-white">Place Waiver Claim</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <FiX size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Player Info Summary */}
          <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
            <p className="text-sm text-slate-400">Targeting:</p>
            <p className="text-lg font-bold text-blue-400">{player.name} <span className="text-sm font-normal text-slate-500">({player.position} - {player.nfl_team})</span></p>
          </div>

          {/* Bid Input */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Bid Amount ($)</label>
            <input 
              type="number" 
              min="0"
              value={bid}
              onChange={(e) => setBid(parseInt(e.target.value) || 0)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
            <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
              <FiInfo size={12} /> Claims are processed based on highest bid.
            </p>
          </div>

          {/* Drop Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Player to Drop (Optional)</label>
            <select 
              value={playerToDrop}
              onChange={(e) => setPlayerToDrop(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-white focus:ring-2 focus:ring-blue-500 focus:outline-none appearance-none"
            >
              <option value="">-- Select a player --</option>
              {userRoster.map(p => (
                <option key={p.id} value={p.id}>{p.name} ({p.position})</option>
              ))}
            </select>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button 
              type="button" 
              onClick={onClose}
              className="flex-1 px-4 py-3 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 transition-all"
            >
              Cancel
            </button>
            <button 
              type="submit"
              className="flex-1 px-4 py-3 rounded-lg bg-blue-600 text-white font-bold hover:bg-blue-500 shadow-lg shadow-blue-900/20 transition-all"
            >
              Submit Claim
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ClaimModal;