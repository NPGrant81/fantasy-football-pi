# UAT Deck Image Coverage

## Purpose
This file defines the screenshot coverage contract for `docs/uat/uat_overview.pptx`.

The goal is to keep the UAT presentation synchronized with:
- `docs/uat/uat_master.xlsx`
- current frontend routes and modal workflows
- documented architecture/page mappings

## Source-of-Truth References
Use these references when adding or changing screenshot coverage:
- `docs/ARCHITECTURE.md`
- `docs/API_PAGE_MATRIX.md`
- `docs/UI_REFERENCE.md`
- `docs/FRONTEND_UI_STANDARDS.md`
- `frontend/src/App.jsx`

## Automation Flow
1. Start frontend: `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173`
2. Capture screenshots: `cd frontend && npx cypress run --spec "cypress/e2e/uat_capture_pages.spec.js"`
3. Update deck images: `python scripts/update_uat_deck_images.py`
4. Verify final slide/image mapping in PowerPoint.

Screenshot source folder:
- `frontend/cypress/screenshots/uat_capture_pages.spec.js/`

## Required Clarity Standards
- Use desktop viewport captures (minimum 1280x720).
- Ensure text/UI controls are readable in the deck image frame.
- Avoid loading spinners or skeleton states in final captured images.
- Re-capture if screenshots are blurry, cropped, or stale.

## Slide-to-Screenshot Mapping
| Slide | Deck Title | Screenshot File |
| --- | --- | --- |
| 4 | Login Page | `uat_login_page.png` |
| 5 | Home Page | `uat_home_page.png` |
| 6 | War Room | `uat_war_room_page.png` |
| 7 | Chat Advisor | `uat_chat_advisor_page.png` |
| 8 | Draft Day Analyzer | `uat_draft_day_analyzer_page.png` |
| 9 | My Team | `uat_my_team_page.png` |
| 10 | Matchups | `uat_matchups_page.png` |
| 11 | Game Center | `uat_game_center_page.png` |
| 12 | Waiver Wire | `uat_waiver_wire_page.png` |
| 13 | Keepers | `uat_keepers_page.png` |
| 14 | Analytics | `uat_analytics_page.png` |
| 15 | Playoff Bracket | `uat_playoff_bracket_page.png` |
| 16 | Commissioner Dashboard | `uat_commissioner_dashboard_page.png` |
| 17 | Commissioner - Manage Owners | `uat_commissioner_manage_owners_page.png` |
| 18 | Commissioner - Lineup Rules | `uat_commissioner_lineup_rules_page.png` |
| 19 | Commissioner - Waiver Rules | `uat_commissioner_waiver_rules_page.png` |
| 20 | Commissioner - Manage Trades | `uat_commissioner_manage_trades_page.png` |
| 21 | Commissioner - Manage Divisions | `uat_commissioner_manage_divisions_page.png` |
| 22 | Admin Settings | `uat_admin_settings_page.png` |
| 23 | Report a Bug + UAT Handoff | `uat_bug_report_page.png` |
| 24 | Key Modals and Overlays | `uat_commissioner_draft_budgets_modal.png` |
| 25 | Trade Proposal Modal | `uat_trade_proposal_modal.png` |
| 26 | Player Season Performance Modal | `uat_player_season_performance_modal.png` |
| 27 | Waiver Wire Modal Targets | `uat_waiver_confirm_modal.png` |

## Modal Coverage Targets
Current modal screenshots included:
- `uat_commissioner_draft_budgets_modal.png`
- `uat_trade_proposal_modal.png`
- `uat_player_season_performance_modal.png`
- `uat_waiver_confirm_modal.png`
- `uat_waiver_drop_player_modal.png`

Waiver capture note:
- When `Claim` controls are available, waiver screenshots represent true modal states.
- When route state suppresses `Claim`, automation emits deterministic fallback captures using the waiver page viewport so deck updates do not fail.

Additional modal targets (capture when route states allow deterministic reproduction):
- Trade proposal submit-success state
- Player season details for alternate positions (QB/RB/TE)
- Commissioner owner-management edit modal

## Update Rules
- Any route/page rename in `frontend/src/App.jsx` requires this mapping to be reviewed.
- Any new user-visible page requires a new screenshot and corresponding deck coverage.
- Any new release-critical modal should either:
  - replace an existing modal capture in slide 24, or
  - add a new modal slide in the deck.
- PRs with user-facing changes are not complete without workbook + deck sync.
