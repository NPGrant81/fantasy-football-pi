# UAT Mock Data

This file documents the JSON structures that the developer should wire into
Locker Room and Match‑up pages for User Acceptance Testing.  These fixtures are
loaded from `src/mock/*.json` and there are helper tests in
`frontend/tests/uat_data.test.jsx` demonstrating how to consume them.

## 1. Locker Room Optimization Check

`src/mock/uat_roster.json` provides a team roster with one optimized slot and
one sub‑optimal slot.  The UI must:

* highlight the bench player **Puka Nacua** with a "Start Suggestion" badge
* mark the WR2 slot as "Sit" because the bench projection (19.5) > current (8.1)
* apply the appropriate color class (e.g. `POSITION_COLORS.WR`) to both slots

### Hook into the fixture
```js
import rosterData from '@mock/uat_roster.json';
// use rosterData.roster in your component state during development / UAT
```

## 2. Match‑ups & Live Scoring

`src/mock/uat_matchup.json` contains two teams with per‑player scores and
total_score fields.  When rendering this structure the page must calculate
`players.reduce((s,p) => s + p.score, 0)` and match the provided `total_score`.
Adopt the JSON object as the canonical source during early testing.

### Example consumption
```js
import matchup from '@mock/uat_matchup.json';
const { home_team, away_team } = matchup;
const homeTotal = home_team.players.reduce((s,p) => s + p.score, 0);
// assert(homeTotal === home_team.total_score);
```

## 3. Position color mapping
Refer to `src/utils/uiHelpers.js` for `POSITION_COLORS`.  UAT fixtures use `WR`
or `RB` etc.  If new positions are added, update the map accordingly.

## 4. Projection vs Actual Data
The file `src/mock/uat_proj_actual.json` models a simple start/sit scenario:

```json
{
  "scenario": "StartSitCheck",
  "players": [
    {
      "id": "201",
      "name": "Saquon Barkley",
      "position": "RB",
      "projected_points": 15.3,
      "actual_points": 11.7,
      "is_recommended": true
    },
    {
      "id": "202",
      "name": "Miles Sanders",
      "position": "RB",
      "projected_points": 9.8,
      "actual_points": 14.2,
      "is_recommended": false
    }
  ]
}
```

Use this fixture to drive highlighting logic. The accompanying test
(`uat_data.test.jsx`) demonstrates the expected relationship between
`projected_points` and the `is_recommended` flag.  The front end should
calculate its own recommendation and compare to the flag for verification.

---

These fixtures serve as the single source of truth for the first sprint's
acceptance criteria.  They are intentionally simple; the backend need not be
running to run the front‑end verifications.
