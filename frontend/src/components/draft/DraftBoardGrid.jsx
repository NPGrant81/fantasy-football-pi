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

  // use flex container with fixed-width columns so every column is identical regardless of content
  return (
    <div className="flex gap-2 p-4 bg-slate-900 w-full overflow-x-auto">
      {teams.map((team) => (
        <div
          key={team.id}
          className={`flex-none w-[110px] flex flex-col border ${
            team.id === highlightOwnerId
              ? 'border-cyan-400'
              : 'border-slate-700'
          }`}
        >
          {/* header area: team name + stats */}
          <div className="flex flex-col items-center p-2 bg-slate-800 border-b border-slate-700">
            {/* allow long names to wrap within the column instead of overflowing */}
            <span className="text-sm font-bold text-white leading-tight break-words whitespace-normal text-center">
              {team.team_name || team.name || team.username}
            </span>
            <span className="text-xs text-green-400 font-medium">
              {rosterMap[team.id]?.length || 0} Drafted | $
              {(team.remaining_budget ?? team.remainingBudget) || 0} Remaining
            </span>
          </div>
          <div className="flex flex-col">
            {[...Array(rosterLimit)].map((_, i) => {
              const player = rosterMap[team.id]?.[i];
              return (
                <div
                  key={i}
                  className={`h-16 flex flex-col justify-center items-center border-r border-b border-slate-700 bg-slate-900 p-1 
                    ${player ? POSITION_COLORS[player.position] || '' : 'bg-slate-900 opacity-50'}`}
                >
                  {player ? (
                    <>
                      <span className="text-sm font-semibold text-slate-100 break-words text-center">
                        {player.player_name || player.name}
                      </span>
                      <span className="text-[10px] text-slate-400 uppercase tracking-tighter mt-1">
                        {player.position ? `${player.position} | ` : ''}
                        {player.amount || player.price
                          ? `$${player.amount || player.price}`
                          : ''}{' '}
                        Drafted
                      </span>
                    </>
                  ) : (
                    <span className="text-xs text-slate-600 font-bold tracking-widest uppercase opacity-30">
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
