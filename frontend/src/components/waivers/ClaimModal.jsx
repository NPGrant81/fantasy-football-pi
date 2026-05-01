import React, { useState } from 'react';
import { FiX, FiInfo } from 'react-icons/fi';
import { modalOverlay } from '@utils/uiStandards';

const ClaimModal = ({
  player,
  isOpen,
  onClose,
  onConfirm,
  userRoster = [],
}) => {
  const [bid, setBid] = useState(1);
  const [playerToDrop, setPlayerToDrop] = useState('');

  if (!isOpen || !player) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    onConfirm({
      playerId: player.id,
      bidAmount: bid,
      dropPlayerId: playerToDrop,
    });
    onClose();
  };

  return (
    <div className={`${modalOverlay} backdrop-blur-sm bg-black/70`}>
      <div className="bg-white border border-slate-200 rounded-xl w-full sm:max-w-md shadow-2xl overflow-hidden dark:bg-slate-900 dark:border-slate-700">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/50">
          <h3 className="text-xl font-bold text-slate-900 dark:text-white">Place Waiver Claim</h3>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-700 transition-colors dark:text-slate-400 dark:hover:text-white"
          >
            <FiX size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Player Info Summary */}
          <div className="bg-slate-100 p-3 rounded-lg border border-slate-300 dark:bg-slate-800/50 dark:border-slate-700/50">
            <p className="text-sm text-slate-600 dark:text-slate-400">Targeting:</p>
            <p className="text-lg font-bold text-blue-600 dark:text-blue-400">
              {player.name}{' '}
              <span className="text-sm font-normal text-slate-500 dark:text-slate-500">
                ({player.position} - {player.nfl_team})
              </span>
            </p>
          </div>

          {/* Bid Input */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-slate-300">
              Bid Amount ($)
            </label>
            <input
              type="number"
              min="0"
              value={bid}
              onChange={(e) => setBid(parseInt(e.target.value) || 0)}
              className="w-full bg-white border border-slate-300 rounded-lg p-3 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none dark:bg-slate-950 dark:border-slate-700 dark:text-white"
            />
            <p className="text-xs text-slate-600 mt-2 flex items-center gap-1 dark:text-slate-500">
              <FiInfo size={12} /> Claims are processed based on highest bid.
            </p>
          </div>

          {/* Drop Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2 dark:text-slate-300">
              Player to Drop (Optional)
            </label>
            <select
              value={playerToDrop}
              onChange={(e) => setPlayerToDrop(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-lg p-3 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none appearance-none dark:bg-slate-950 dark:border-slate-700 dark:text-white"
            >
              <option value="">-- Select a player --</option>
              {userRoster.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.position})
                </option>
              ))}
            </select>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-3 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 transition-all dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
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
