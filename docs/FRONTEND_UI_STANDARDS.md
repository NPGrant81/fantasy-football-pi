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
| `WaiverWire` | Updated | Standardized shell/header, draft-lock surface, and confirm modal actions. |
| `Waiver` child components | Updated | `WaiverTable`, `WaiverPositionTabs`, and `DropPlayerModal` aligned to shared table/modal/button tokens. |
| `WaiverRules` | Updated | Standardized shell/header/card/actions with light/dark-safe route typography. |
| `SiteAdmin` | Updated | Standardized shell/header and typography while preserving admin action cards. |
| `ManageCommissioners` | Updated | Standardized shell/header, forms, table surfaces/head, and action buttons. |
| `Matchups` | Updated | Replaced legacy split header with shared shell/header/title/subtitle and standardized context cards. |
| `GameCenter` | Updated | Standardized shell/header and matchup banner heading contrast in both themes. |
| `BugReport` | Updated | Standardized shell/header/form controls and removed legacy hardcoded title color. |
| `Sidebar` | Updated | Theme-safe container/header/footer and unified nav active/hover states with standardized slate/cyan palette. |
| Remaining route pages | Partial | Major high-traffic pages aligned; continue component-level convergence. |

## Next Sweep Candidates

1. Waiver `ClaimModal` tokenization pass
2. Final `MyTeam` deep-module pass (remaining module-level surface consistency)
3. `DraftBoard` child components (`AuctionBlock`, `SessionHeader`, lists) — deferred per current scope

Status note: shared admin/component pass is now implemented under strict token usage.

## Theme Toggle Smoke Checklist (Per Touched Route)

1. Toggle dark → light and verify page title remains readable.
2. Verify subtitle and metadata text keep contrast on both themes.
3. Verify primary and secondary actions remain visually distinct.
4. Verify table headers/rows remain readable and focus states visible.
