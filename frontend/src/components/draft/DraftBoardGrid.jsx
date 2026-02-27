import React, { useMemo } from 'react';
import { POSITION_COLORS } from '@/constants/ui';

/**
 * teams: array of owner objects { id, name, remainingBudget }
 * history: array of draft events { owner_id, player_name, position, amount }
 * rosterLimit: number of roster slots (e.g. 14)
 */
export default function DraftBoardGrid({
  teams = [],
  history = [],
  rosterLimit = 14,
  highlightOwnerId = null,
}) {
  const rosterMap = useMemo(() => {
    const map = {};
    teams.forEach((t) => (map[t.id] = []));
    history.forEach((h) => {
      if (map[h.owner_id]) {
        map[h.owner_id].push(h);
      }
    });
    return map;
  }, [teams, history]);

  return (
    <div className="grid grid-cols-12 gap-2 p-4 bg-slate-900 w-full overflow-x-auto">
      {teams.map((team) => (
        <div
          key={team.id}
          className={`flex flex-col border min-w-[110px] ${
            team.id === highlightOwnerId
              ? 'border-cyan-400'
              : 'border-slate-700'
          }`}
        >
          <div className="bg-slate-800 p-2 text-center border-b border-slate-700">
            <h3 className="font-bold text-xs uppercase truncate text-white">
              {team.name}
            </h3>
            <p className="text-[10px] text-green-400 font-mono">
              {(rosterMap[team.id]?.length || 0)}&nbsp;|&nbsp;${(team.remaining_budget ?? team.remainingBudget) || 0}
            </p>
          </div>
          <div className="flex flex-col">
            {[...Array(rosterLimit)].map((_, i) => {
              const player = rosterMap[team.id]?.[i];
              return (
                <div
                  key={i}
                  className={`h-12 border-b border-slate-800 p-1 flex flex-col justify-center text-[10px] 
                    ${player ? POSITION_COLORS[player.position] : 'bg-slate-900 opacity-50'}`}
                >
                  {player ? (
                    <>
                      <span className="font-bold truncate leading-tight">
                        {player.player_name || player.name}
                      </span>
                      <div className="text-[10px] mt-1 opacity-90">
                        {player.position} | ${player.amount || player.price}
                      </div>
                    </>
                  ) : (
                    <span className="text-slate-700 italic text-center text-[8px]">
                      OPEN
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
