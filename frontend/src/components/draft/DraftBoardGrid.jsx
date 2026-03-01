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
  onPlayerClick,
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
    <div
      data-testid="draft-board"
      className="flex gap-1 p-4 bg-slate-900 w-full overflow-x-auto md:flex"
    >
      {teams.map((team) => (
        <div
          key={team.id}
          className={`flex-1 min-w-0 flex flex-col border ${
            team.id === highlightOwnerId
              ? 'border-cyan-400'
              : 'border-slate-700'
          }`}
        >
          {/* header area: team name + stats */}
          <div className="flex flex-col items-center p-2 bg-slate-800 border-b border-slate-700 h-24 justify-between">
            {/* allow long names to wrap within the column instead of overflowing (fixed height keeps all headers equal) */}
            <span className="text-sm font-bold text-white leading-tight break-words whitespace-normal text-center">
              {team.team_name || team.name || team.username}
            </span>
            <span className="text-xs text-green-400 font-medium">
              {rosterMap[team.id]?.length || 0} | $
              {(team.remaining_budget ?? team.remainingBudget) || 0} Remaining
            </span>
          </div>
          <div className="flex flex-col">
            {[...Array(rosterLimit)].map((_, i) => {
              const player = rosterMap[team.id]?.[i];
              return (
                <div
                  data-testid={player ? 'player-card' : undefined}
                  key={i}
                  onClick={() => {
                    if (player && onPlayerClick) onPlayerClick(player);
                  }}
                  onKeyDown={(event) => {
                    if (!player || !onPlayerClick) return;
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onPlayerClick(player);
                    }
                  }}
                  role={player ? 'button' : undefined}
                  tabIndex={player ? 0 : undefined}
                  className={(() => {
                    if (!player) {
                      return 'h-24 flex flex-col justify-center items-center border-r border-b border-slate-700 p-2 bg-slate-900 opacity-50';
                    }
                    const bg =
                      POSITION_COLORS[player.position] || 'bg-yellow-400';
                    // base background matches position, add thin gold border for emphasis
                    return `h-24 flex flex-col justify-between items-center border-r border-b border-slate-700 p-2 ${bg} text-slate-100 border-2 border-slate-600 rounded-md shadow-md cursor-pointer hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-cyan-400/60`;
                  })()}
                >
                  {player ? (
                    (() => {
                      const full = player.player_name || player.name || '';
                      const parts = full.split(' ');
                      const first = parts.shift() || '';
                      const last = parts.join(' ') || first;
                      return (
                        <>
                          {/* top row: first name and cost */}
                          <div className="w-full flex justify-between items-start">
                            <span className="text-sm font-semibold leading-tight truncate">
                              {first}
                            </span>
                            <span className="text-sm font-bold leading-tight">
                              {player.amount || player.price
                                ? `$${player.amount || player.price}`
                                : ''}
                            </span>
                          </div>
                          {/* bottom: last name large */}
                          <div className="w-full mt-1">
                            <span className="block text-lg font-bold uppercase break-words">
                              {last.toUpperCase()}
                            </span>
                          </div>
                        </>
                      );
                    })()
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
