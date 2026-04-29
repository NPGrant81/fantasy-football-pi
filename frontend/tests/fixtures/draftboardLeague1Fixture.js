export const league1OwnersFixture = [
  { id: 1, username: 'nickgrant', team_name: 'War Room Alpha' },
  { id: 2, username: 'mikev', team_name: 'Gridiron Guild' },
  { id: 3, username: 'samj', team_name: 'Fourth and Longshots' },
  { id: 4, username: 'ajayk', team_name: 'Sunday Stackers' },
  { id: 5, username: 'liamr', team_name: 'Waiver Wire Wizards' },
  { id: 6, username: 'camd', team_name: 'Red Zone Renegades' },
  { id: 7, username: 'tonyb', team_name: 'Bench Mob' },
  { id: 8, username: 'derekp', team_name: 'The Audible' },
  { id: 9, username: 'kevins', team_name: 'Two Minute Drill' },
  { id: 10, username: 'nataliec', team_name: 'Goal Line Stand' },
  { id: 11, username: 'ryanm', team_name: 'Dynasty Depot' },
  { id: 12, username: 'zoel', team_name: 'Commissioner Chaos' },
];

export const league1BudgetsFixture = league1OwnersFixture.map((owner) => ({
  owner_id: owner.id,
  total_budget: 200,
}));

export const league1PlayersFixture = [
  { id: 101, name: 'Josh Allen', position: 'QB', nfl_team: 'BUF' },
  { id: 202, name: 'Bijan Robinson', position: 'RB', nfl_team: 'ATL' },
  { id: 303, name: 'JaMarr Chase', position: 'WR', nfl_team: 'CIN' },
  { id: 404, name: 'Sam LaPorta', position: 'TE', nfl_team: 'DET' },
];

export const league1SettingsFixture = {
  draft_year: 2026,
  roster_size: 16,
};

export const league1MetaFixture = {
  id: 1,
  name: 'League 1',
};
