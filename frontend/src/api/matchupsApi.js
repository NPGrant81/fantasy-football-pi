import { getJson } from '@api/fetching';

export function fetchWeekMatchups(week) {
  return getJson(`/matchups/week/${week}`, { retries: 1 });
}
