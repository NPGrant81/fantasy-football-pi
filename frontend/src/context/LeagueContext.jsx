import { createContext, useContext } from 'react';

export const LeagueContext = createContext({
  activeLeagueId: null,
});

export function useActiveLeague() {
  const context = useContext(LeagueContext);
  if (!context) {
    // Fallback to localStorage when context is not available
    // This should rarely happen in production but serves as safety net
    const leagueId = localStorage.getItem('fantasyLeagueId');
    return leagueId ? String(leagueId) : null;
  }
  return context.activeLeagueId;
}
