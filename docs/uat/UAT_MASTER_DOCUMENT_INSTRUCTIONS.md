# UAT Master Document Instructions

## Purpose
This document defines how QA testers and Copilot should generate, maintain, and execute UAT test cases for the Fantasy Football Pi application.

Primary output target:
- `docs/uat/uat_master.xlsx`
- `docs/uat/uat_overview.pptx`

This markdown file is the process guide and quality bar. The spreadsheet is the execution artifact and source of truth for run status. The presentation is the visual onboarding artifact and must stay aligned with workbook coverage.

## Baseline Environment
- UAT baseline is `CERT` (certification stage) and should represent production-like behavior for end users.

## Spreadsheet Schema (Current)
`uat_master.xlsx` currently uses these columns on `Sheet1`:

| Column | Header | Required | Description |
| --- | --- | --- | --- |
| A | AREA | Yes (section rows) | Section label rows (example: `Login Page - <blurb>`). |
| B | ID | Yes | Test case ID in `X.YY` format (example: `1.01`). Must be treated as text. |
| C | Page | Yes | Sub-area or page context (example: `Login`, `Navigation`, `Lineup`). |
| D | step# | Yes | Step sequence number within the test case grouping. |
| E | Test Step | Yes | Action performed by tester. |
| F | Expected Result | Yes | Expected behavior or output. |
| G | Expected Status | Yes | Execution state: `Not Tested`, `In Progress`, `Pass`, `Fail`, or `Blocked`. |
| H | Actual Result | Conditionally | Required when status is `Fail` or `Blocked`; optional otherwise. |
| I | Priority Level | Yes | `High`, `Medium`, `Low`, or `N/A` where truly applicable. |
| J | Solution | Conditionally | Proposed fix/workaround for `Fail` or `Blocked`. |
| K | Fix Applied | Conditionally | Fix status (`Yes/No/Partial`) and short note. |
| L | Role Scope | Yes | Primary role under test (`User`, `Commissioner`, `Site Admin`, `Mixed`). |
| M | Traceability ID | Yes (action rows) | Links row to portfolio story and owning code area. |
| N | Bug Ticket | Conditionally | GitHub issue ID/link when a defect is raised. |
| O | Code Path Default | Yes (action rows) | Suggested frontend file path for fix ownership and triage routing. |
| P | Execution Tier | Yes | Run order for QA execution (`P0 - Critical Path`, `P1 - Core Regression`, `P2 - Extended Coverage`). |

## Critical Data Rules
1. IDs must be stored as text, not numeric values.
2. IDs must use two decimals (for example `2.01`, not `2.0099999999999998`).
3. Every section row in column A must replace placeholder blurbs with actual page purpose text.
4. `Expected Status` is the execution status field. Use one controlled vocabulary: `Not Tested`, `In Progress`, `Pass`, `Fail`, `Blocked`.
5. If status is `Fail` or `Blocked`, columns `H`, `J`, and `K` must be completed.
6. Dropdown lists must be used for controlled fields to improve multi-tester consistency.

## UAT Execution Workflow
### 1) Prepare Environment
- Use the agreed UAT environment (`CERT`, production-like for end users).
- Ensure data fixtures exist (owners, rosters, matchups, standings, waivers, keepers).
- Verify user role for the scenario under test (User, Commissioner, Site Admin).
- Confirm external dependencies needed for scenario are available (AI, integrations, etc.).

### 2) Run Test Cases
- Execute each row exactly as written in `Test Step`.
- Compare behavior to `Expected Result` only.
- Update `Expected Status` after execution.
- For failures, capture reproducible evidence (screenshot/log/API response).
- Document actual behavior in `Actual Result`.

### 3) Log Defects
- Create GitHub issue when status is `Fail` or `Blocked` and problem is product-related.
- Add issue link/ID in `Solution` or `Fix Applied` notes.
- Re-test after fix and update status.

### 4) Aggregate Defect Feedback
- Use a dedicated roll-up tab (`Defect_Rollup`) to consolidate defects from all tester forms.
- Each defect should be de-duplicated and assigned a single master tracking ID.
- Keep per-row UAT context in `Sheet1` and master defect triage in `Defect_Rollup`.

## Test Authoring Rules (Copilot + QA)
Plain-language requirement:
- Write for non-technical testers and end users.
- Prefer words like `sign in`, `screen`, `page`, `button`, `save`, and `refresh`.
- Avoid engineering terms in tester-facing steps/results (for example `token`, `endpoint`, `route`, `console`, `payload`).
- Prefer navigation wording users see in the app (example: `Menu > War Room`, `Commissioner > Manage Owners`).

Copilot should:
- Rewrite ambiguous steps into explicit, testable actions.
- Add missing negative/validation scenarios where implied by feature behavior.
- Keep wording concise and deterministic.
- Preserve all existing business rules from code and documentation.
- Flag assumptions instead of inventing functionality.

Copilot should not:
- Invent hidden requirements.
- Add unsupported API/UI behavior.
- Mark tests as passed without explicit run evidence.

## Coverage Requirements
Each major feature area should include at least:
- Happy path
- Validation/negative path
- Permission boundary path (where roles differ)
- Empty/loading/error state (where applicable)
- Data persistence/state continuity check (refresh/navigation)

Execution priority must be decided in UAT planning (not deferred to backend triage):
- `P0 - Critical Path`: login/session, access control, core in-season workflows.
- `P1 - Core Regression`: major page workflows and high-traffic components.
- `P2 - Extended Coverage`: lower-risk and edge/polish scenarios.

For AI/Chat scenarios, include software-standard NFR checks:
- Response time target under normal load (target: <= 3 seconds for standard prompts)
- Graceful timeout/error behavior
- Repeatability of answer format for similar prompts

Use these project references when expanding cases:
- `docs/API_PAGE_MATRIX.md`
- `docs/permissions.md`
- `docs/PROJECT_MANAGEMENT.md`

Use these project references when maintaining presentation screenshot coverage:
- `docs/ARCHITECTURE.md`
- `docs/API_PAGE_MATRIX.md`
- `docs/UI_REFERENCE.md`
- `docs/FRONTEND_UI_STANDARDS.md`
- `docs/uat/UAT_DECK_IMAGE_COVERAGE.md`

## Mapping to Feature Areas
Use the existing numbering convention:
- `1.xx` Login and Session
- `2.xx` Home
- `3.xx` My Team
- `4.xx` Match-up and Game Center
- `5.xx` Cross-cutting quality
- `6.xx` Full frontend page coverage
- `7.xx` Full frontend component coverage

When adding new areas, reserve next major block (`5.xx`, `6.xx`, etc.) and document in change log.

## Traceability Standard (Portfolio and Code)
Every actionable UAT row should include a traceability ID to map defects and fixes back to delivery artifacts.

Recommended format:
- `TRC-<Story>-<Area>-<ID>`
- Example: `TRC-6.1-MATCHUPS-4.05`

Suggested source mapping references:
- Story map: `docs/PROJECT_MANAGEMENT.md`
- API/page map: `docs/API_PAGE_MATRIX.md`
- Code path (example): `frontend/src/pages/matchups/Matchups.jsx`

If a row produces a defect, include:
- Traceability ID
- GitHub issue ID/link
- Candidate code path(s) for fix ownership

## Row Quality Checklist
Before adding or updating a test row, verify:
- ID format is valid and text-typed.
- Step is actionable by a human tester.
- Expected result is observable and measurable.
- Role assumptions are clear or documented.
- Priority is assigned consistently.
- Execution Tier is assigned and aligned with run order (`P0` before `P1` before `P2`).
- Failure-handling columns are defined for execution follow-up.
- Evidence is attached for `Fail` and `Blocked`; evidence for `Pass` is strongly recommended on high-risk scenarios.

## After Testing: How to Hand Results Back
When testers complete a pass in `uat_master.xlsx`, return results in one of these ways:
1. Save the updated workbook in `docs/uat/uat_master.xlsx` and ask Copilot to "review latest UAT results".
2. If testers used separate copies, merge failures into `Defect_Rollup` first, then ask Copilot to summarize and de-duplicate.
3. Provide the test window scope in your prompt (example: `P0 only`, `rows 1.01-6.24`, or `all Commissioner tests`).

What Copilot can do next:
- Summarize defects by severity, area, and owner path.
- Detect likely duplicates in `Defect_Rollup`.
- Produce release gate status (`P0 pass/fail/blockers`).
- Draft GitHub issue content using row evidence.

## Presentation Sync Workflow (Required)
For any user-facing route, modal, or workflow change:
1. Update `docs/uat/uat_overview.pptx` in the same PR as workbook updates.
2. Refresh screenshots using `frontend/cypress/e2e/uat_capture_pages.spec.js`.
3. Re-apply screenshots using `scripts/update_uat_deck_images.py`.
4. Validate slide coverage against `docs/uat/UAT_DECK_IMAGE_COVERAGE.md`.
5. If new routes/modals are added, extend both screenshot capture spec and coverage mapping doc.

## Decisions Captured
1. Baseline UAT environment is `CERT`.
2. Status values are controlled and should be dropdown-driven for tester consistency.
3. `Priority Level` may use `N/A` for informational/non-action rows; action rows must be `Low`, `Medium`, or `High`.
4. Maintain a master defect roll-up list to aggregate issues from multiple tester forms.
5. AI/chat SLA should follow software standard NFR checks.
6. Evidence policy follows best practice: mandatory for `Fail/Blocked`, strongly recommended for high-risk `Pass` cases.
7. Page-purpose blurbs are mandatory to provide tester context.
8. Traceability IDs are required for actionable rows to map back to portfolio and code ownership.

## Immediate Cleanup Tasks in `uat_master.xlsx`
1. Convert all ID cells in column B to text and normalize values like `2.0099999999999998` to `2.01`.
2. Replace placeholder blurbs in section rows (`Login Page`, `Home Page`, `My Team Page`, `Match-up Page`) with actual descriptions.
3. Add dropdown validation in controlled fields (`Expected Status`, `Priority Level`, `Fix Applied`).
4. Add traceability and defect linkage columns for actionable rows.
5. Create and maintain a `Defect_Rollup` tab for consolidated triage.

## Change Log
- 2026-03-07: Initial robust instruction set created for generating and maintaining `uat_master.xlsx`.
- 2026-03-07: Updated with CERT baseline, dropdown standards, defect roll-up workflow, traceability ID rules, and evidence policy.
- 2026-03-07: Added required sync policy for `uat_overview.pptx` and screenshot automation workflow.
