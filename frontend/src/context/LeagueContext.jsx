import { createContext, useContext } from 'react';

export const LeagueContext = createContext({
  activeLeagueId: null,
});

export function useActiveLeague() {
  const { activeLeagueId } = useContext(LeagueContext);
  if (activeLeagueId !== null && activeLeagueId !== undefined) {
    return String(activeLeagueId);
  }
  // Fallback to localStorage when context has no active league.
  // App.jsx clears localStorage when activeLeagueId becomes null,
  // so this returns null in production when no league is selected.
  const stored = localStorage.getItem('fantasyLeagueId');
  return stored ? String(stored) : null;
}
