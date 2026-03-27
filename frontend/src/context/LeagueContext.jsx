import { createContext, useContext } from 'react';

export const LeagueContext = createContext(null);

export function useActiveLeague() {
  const ctx = useContext(LeagueContext);
  const activeLeagueId = ctx?.activeLeagueId ?? null;
  if (activeLeagueId !== null && activeLeagueId !== undefined) {
    return String(activeLeagueId);
  }
  // Fallback to localStorage when context has no active league.
  // App.jsx clears localStorage when activeLeagueId becomes null,
  // so this returns null in production when no league is selected.
  if (typeof window === 'undefined' || !window.localStorage) return null;
  const stored = window.localStorage.getItem('fantasyLeagueId');
  return stored ? String(stored) : null;
}
