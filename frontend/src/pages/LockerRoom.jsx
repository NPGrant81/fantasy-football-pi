import React, { useState, useCallback } from 'react';
import { swapPlayers } from '@utils/rosterHelpers';
import { POSITION_COLORS } from '@utils/uiHelpers';

// --- 1. A skeleton LockerRoom page used during the roster-engine sprint ---
export default function LockerRoom({ initialRoster = [] }) {
  // roster is an array of slots; empty slots are null
  const [roster, setRoster] = useState(initialRoster);

  const onDrop = useCallback((dragIdx, dropIdx) => {
    const newRoster = swapPlayers(roster, dragIdx, dropIdx);
    setRoster(newRoster);
    // TODO: patch backend with newRoster array
  }, [roster]);

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold mb-4">Locker Room (Draft day)</h2>
      <div className="grid grid-cols-3 gap-4">
        {roster.map((slot, idx) => (
          <div
            key={idx}
            data-slot-index={idx}
            className={`relative border rounded p-2 h-24 flex items-center justify-center cursor-pointer ${
              slot ? POSITION_COLORS[slot.position] : 'border-red-500 animate-pulse'
            }`}
            // drag/drop handlers would go here
          >
            {slot ? slot.name : 'EMPTY'}
            {/* status ring could be an absolute element */}
            <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-green-400"></div>
          </div>
        ))}
      </div>
    </div>
  );
}
