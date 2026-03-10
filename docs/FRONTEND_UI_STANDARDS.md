# Frontend UI Standards (Compact Enterprise)

## Baseline Decisions

- Visual base: compact enterprise style layered over existing app shell.
- Typography direction: keep strong weight, reduce uppercase/italic to page accents only.
- Priority domains: global shell/page headers, then buttons/forms, then cards/tables.
- Rollout mode: full sweep using shared primitives and page-by-page convergence.
- Token enforcement mode: gradual (all new/edited pages must use shared primitives).

## Recent Implementation Updates

- Global top sub-header row removed from active app flow to eliminate dead vertical space and keep page titles consistently anchored.
- Strict shared component pass completed for `AdminActionCard` and commissioner modals.
- Theme-toggle route sweep completed for title/root contrast risks; outliers corrected.
- `MyTeam` tranche 1 completed for high-impact modals/forms/buttons using shared modal + input/button primitives.
- `MyTeam` layout refinement: removed redundant Start/Sit control row and consolidated week/sort/view/submit controls into the Lineup Builder header.
- `MyTeam` tranche 2 completed for lineup/recommendation/sit-rep card surfaces and row-level contrast harmonization.
- Reusable `PlayerIdentityCard` component added for modal player profiles; MyTeam season modal now consumes API-provided headshot metadata.
- Finite pass complete: back-button color standardization (non-DraftBoard routes) and sidebar color/state standardization.
- Waiver child components standardized: `WaiverTable`, `WaiverPositionTabs`, and `DropPlayerModal` now use shared tokenized surfaces/buttons.
- DraftBoard enhancement: clicking drafted player cards now opens the shared Season Performance modal pattern; `PlayerIdentityCard` updated to larger headshot + stronger position/name hierarchy.
- PageTemplate tranche started for remaining legacy routes: `Keepers`, `CommissionerDashboard`, and `ManageOwners` now use shared page-header contracts.
- PageTemplate route-header sweep completed for legacy admin/commissioner/owner routes (`Home`, `WaiverWire`, `GameCenter`, `SiteAdmin`, `ManageCommissioners`, `ManageTrades`, `ManageWaiverRules`, `LedgerStatement`, `LineupRules`, `ManageDivisions`, `ManageKeeperRules`, `ManageScoringRules`, `DraftBoard`, `YourLockerRoom`).
- Stage 2 tracking issue opened: #204 (`Typography, Tables, Shared Components`). Initial tranche adds shared typography tokens (`textBody`, `textMuted`, `textMeta`, `textCaption`) and reusable table primitives (`TablePrimitives`) adopted in commissioner pages (`ManageTrades`, `LedgerStatement`, `ManageWaiverRules`).
- Stage 2 expansion completed for additional admin/commissioner table-heavy pages (`ManageCommissioners`, `ManageOwners`, `ManageDivisions`, `ManageScoringRules`, `ManageKeeperRules`, `team-owner/LedgerStatementOwner`) using shared table primitives and text tokens.
- Phase 3 follow-on issue opened: #205 (`Layering, Theme Polish, Rendering UX`) with dedicated tracks for dropdown front-layer reliability, overlap prevention, spacing rules, toast contract, and load-state consistency.
- Phase 3 tranche 1 delivered: shared layering token scale and spacing scale contracts added in `uiStandards` (`layerNav`, `layerBackdrop`, `layerDrawer`, `layerDropdown`, `layerModal`, `layerToast`, `stackSpacing*`).
- Overlay reliability baseline added with `FloatingLayer` portal primitive; `GlobalSearch` and DraftBoard `AuctionBlock` suggestion menus now render through the portal to avoid parent clipping and stacking-context conflicts.
- Shell/overlay adopters aligned to layer tokens (`Layout`, `Sidebar`, `Toast`) to remove hardcoded z-index values.
- Alignment matrix below is kept current as route/component layers are standardized.

## Core Standards

### 1) Page Layout

- Page root uses: `w-full p-4 md:p-6 space-y-6`.
- Every route page has a header block with:
  - Title: `text-2xl md:text-3xl font-black tracking-tight`
  - Subtitle: `text-sm text-slate-600 dark:text-slate-400`
- Global top alert/sub-header row is disabled for normal routes to keep title placement consistent and eliminate dead space.
- Content regions use card/table surfaces (below), not ad-hoc wrappers.

### 2) Typography

- Route-level `h1`: `text-2xl md:text-3xl font-black tracking-tight`.
- Section `h2`: `text-lg font-bold`.
- Uppercase/italic is optional and scoped to badges/feature accents, not default headings.

### 3) Colors & Surfaces

- Use semantic slate/cyan/red system from Tailwind + project tokens.
- Card surface: rounded, bordered, subtle contrast layer for dark/light.
- Avoid one-off gradients for primary controls unless feature-specific.

### 4) Buttons

- Use shared variants:
  - Primary (cyan)
  - Secondary (neutral slate)
  - Danger (red)
- Maintain consistent radius, font weight, and focus-ring behavior.

### 4.1) Shared Component Contracts

- `AdminActionCard` uses tokenized `tone` variants (no per-page class-string accents).
- Commissioner modals use shared modal primitives (`modalOverlay`, `modalSurface`, `modalTitle`, etc.).
- Player profile modals use shared `PlayerIdentityCard` for name hierarchy, position metadata, and headshot rendering.
- Shared components must consume `uiStandards` exports instead of hardcoded color/spacing strings.

### 5) Forms

- Inputs/selects use one base class for border, bg, text, and focus treatment.
- Labels use consistent weight/size and spacing (`mb-2`, `mb-4`).

### 6) Tables

- Always wrapped in overflow container.
- Shared table head treatment and row borders across pages.

### 7) Theme Safety

- Route-level titles/subtitles must use contrast-safe classes (`pageTitle`, `pageSubtitle`).
- Avoid root-level hardcoded `text-white` on full-page wrappers.
- Theme toggles must preserve title readability and metadata contrast.

### 8) Governance

- Every styling PR that touches routes updates this matrix.
- Theme-toggle smoke checks are required for touched routes (light and dark).
- Responsive audit remains active in CI.

### 9) Layering and Spacing Guardrails

- Use layer tokens from `uiStandards`; do not hardcode arbitrary z-index values in route/component markup.
- Dropdowns and popovers that can be clipped by parent containers should use the shared portal primitive (`FloatingLayer`).
- Layer order baseline:
  - `layerNav` < `layerBackdrop` < `layerDrawer` < `layerDropdown` < `layerModal` < `layerToast`
- Use stack spacing tokens (`stackSpacingXs|Sm|Md|Lg|Xl`) for standardized vertical rhythm in new/edited route sections.

### 10) Toast Contract

- Use `Toast` with explicit type contract: `success | error | warning | info | loading`.
- Dismiss policy baseline:
  - `loading` defaults to sticky (manual close).
  - non-loading variants auto-dismiss unless `sticky` is set.
- Accessibility baseline:
  - `aria-live="assertive"` for `error`.
  - `aria-live="polite"` for non-error toasts.
  - Escape key should dismiss active toast.

### 11) Loading/Empty/Error Contract

- Use shared async state primitives from `frontend/src/components/common/AsyncState.jsx`:
  - `LoadingState`
  - `EmptyState`
  - `ErrorState`
- New/edited pages should avoid ad-hoc plain-text loading/empty/error placeholders when these primitives apply.
- Distinguish async states explicitly:
  - loading: active in-flight operation
  - empty: successful fetch with no items
  - error: failed fetch or action

## Shared Primitive Source

- `frontend/src/utils/uiStandards.js`

This file provides reusable class contracts for shell, headers, cards, tables, inputs, and buttons.

## Current Alignment Matrix

| Area/Page | Status | Notes |
| --- | --- | --- |
| `Layout` shell | Updated | Empty alert row removed; conditional alert bar eliminates dead top spacing globally. |
| `Home` | Updated | Migrated to shared shell/header/table/card treatments. |
| `AnalyticsDashboard` | Updated | Migrated from custom CSS/button-row style to shared shell/buttons/cards. |
| `CommishAdmin` | Updated | Replaced oversized ad-hoc green tiles with standardized action grid. |
| `ManageTrades` | Updated | Standardized page header, table surface, and action buttons. |
| `ManageWaiverRules` | Updated | Standardized form controls, tables, and typography hierarchy. |
| `TablePrimitives` | Updated | Shared table container/head/row/state components introduced and adopted in commissioner migration tranche. |
| `PlayoffBracket` | Updated | Standardized page header and card wrapping of bracket content. |
| `Dashboard` | Updated | Placeholder aligned with shared shell and card style. |
| `LockerRoom` | Updated | Placeholder aligned with shared shell and card style. |
| `DraftBoard` | Updated | Standardized shell/header and added click-to-open player Season Performance modal from draft cards. |
| `MyTeam` | Updated | Header/shell/actions aligned; tranche 1 + tranche 2 completed (modals/forms/buttons, control consolidation, lineup/recommendation/sit-rep card harmonization). |
| `Keepers` | Updated | Header/title now use shared primitives and light/dark-safe text tokens. |
| `CommissionerDashboard` | Updated | Replaced legacy all-caps white header with shared shell/header/title/subtitle. |
| `ManageOwners` | Updated | Standardized shell/header/forms/table/actions with shared primitives. |
| `LineupRules` | Updated | Standardized shell/header, form controls, and save actions with shared tokens. |
| `ManageScoringRules` | Updated | Standardized shell/header/form/table/actions and removed legacy hardcoded title styles. |
| `ManageKeeperRules` | Updated | Standardized shell/header/form/table/actions and improved light/dark contrast safety. |
| `LedgerStatementOwner` | Updated | Owner ledger now uses shared table primitives and Stage 2 text tokens. |
| `WaiverWire` | Updated | Standardized shell/header, draft-lock surface, and confirm modal actions. |
| `Waiver` child components | Updated | `WaiverTable`, `WaiverPositionTabs`, and `DropPlayerModal` aligned to shared table/modal/button tokens. |
| `WaiverRules` | Updated | Standardized shell/header/card/actions with light/dark-safe route typography. |
| `SiteAdmin` | Updated | Standardized shell/header and typography while preserving admin action cards. |
| `ManageCommissioners` | Updated | Standardized shell/header, forms, table surfaces/head, and action buttons. |
| `Matchups` | Updated | Replaced legacy split header with shared shell/header/title/subtitle and standardized context cards. |
| `GameCenter` | Updated | Standardized shell/header and matchup banner heading contrast in both themes. |
| `BugReport` | Updated | Standardized shell/header/form controls and removed legacy hardcoded title color. |
| `Sidebar` | Updated | Theme-safe container/header/footer and unified nav active/hover states with standardized slate/cyan palette. |
| Remaining route pages | Updated | Route-level page header contract migration is complete for current pages; continue component-level convergence. |

## Next Sweep Candidates

1. Phase 3 layering safety pass: z-index token scale + dropdown/popover front-layer reliability
2. Phase 3 spacing rules/guidelines codification with examples and guardrails
3. Phase 3 rendering UX pass: shared loading/empty/error contracts and toast standardization

Status note: shared admin/component pass is now implemented under strict token usage.

## Post-Sweep Verification (Criticality-Based)

Use this checklist to run a full-site verification pass after any major UI standardization sweep.

### Criticality Tiers

- Tier 0 (critical path): login/auth shell, `Home`, `DraftBoard`, `WaiverWire`, `MyTeam`/`YourLockerRoom`, commissioner controls (`CommissionerDashboard`, `ManageScoringRules`, `ManageOwners`, `ManageWaiverRules`), `Matchups`, `GameCenter`.
- Tier 1 (high visibility): `DraftDayAnalyzer`, `Keepers`, `LedgerStatement`, `LedgerStatementOwner`, `PlayoffBracket`, `SiteAdmin`, `ManageCommissioners`, `ManageTrades`, `ManageDivisions`, `LineupRules`, `ManageKeeperRules`.
- Tier 2 (supporting): `BugReport`, `Dashboard`, `LockerRoom`, auxiliary overlays and helper components.

### Full-Site Sweep Checklist

1. Stage 1 contract check:
Route pages should use `PageTemplate` + standardized title/subtitle/metadata conventions.
2. Stage 2 token check:
Route-level tables use shared table primitives/tokens (`TablePrimitives`, `tableCell*`, `tableHead`, `tableRow`, `tableStateCell`).
3. Stage 3 layering check:
No hardcoded fixed-overlay z-index values; use layer tokens (`layerNav`..`layerToast`) and portal overlays (`FloatingLayer`) where clipping risk exists.
4. Theme and contrast check:
Run the Theme Toggle Smoke Checklist below for all Tier 0 pages and touched Tier 1 pages.
5. Interaction safety check:
Dropdowns/popovers/modals/toasts do not clip under headers/drawers and remain usable on small viewports.
6. State rendering check:
Loading, empty, error, and success states are visually distinct and layout-stable.
7. Regression checks:
Run focused test suites for touched routes/components and run `npm run build` before closure.

### Closure Criteria For Sweep Completion

- All Tier 0 pages pass checklist items 1-7.
- All changed Tier 1 pages pass checklist items 1-7.
- No new hardcoded fixed-overlay z-index classes introduced in touched files.
- Documentation and GitHub issue comments are updated with validation evidence.

## Phase 4 Decision

- Not required to mark Stages 1-3 complete.
- Optional if you want a dedicated quality-hardening cycle focused on a11y audits, visual regression automation, and performance budgets.

## Theme Toggle Smoke Checklist (Per Touched Route)

1. Toggle dark → light and verify page title remains readable.
2. Verify subtitle and metadata text keep contrast on both themes.
3. Verify primary and secondary actions remain visually distinct.
4. Verify table headers/rows remain readable and focus states visible.
