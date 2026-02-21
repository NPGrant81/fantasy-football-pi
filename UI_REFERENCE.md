# UI Reference (Consolidated)

This file consolidates the prior `UI_EVALUATION.md` and `FRONTEND_UI_NOTES.md` into a single working reference.

## Scope

- Primary focus: `frontend/src/App.jsx`
- Covers: auth/login UX, accessibility, loading states, routing flow, testing, and maintainability

## Current App Flow

`App.jsx` currently manages three states:

1. Unauthenticated user → Login form
2. Authenticated user without active league → `LeagueSelector`
3. Authenticated user with league → `Layout` + routed pages

Strengths:
- Good base dark-theme contrast and visual hierarchy

## High-Impact Improvements

### 1) Login form validation + loading feedback

Problems:
- Generic error feedback

Recommendations:
- Distinguish error types (`401`, network, throttling, server)

### 2) Initial auth-check loading state

Problems:
- Potential blank/flicker while `/auth/me` resolves

Recommendations:
- Show a small loading shell while token validation is in flight

### 3) Responsive login container

Problems:
- Fixed width patterns are fragile on narrow screens

Recommendations:
- Keep spacing responsive (`p-6 sm:p-8`)

### 4) Accessibility pass

Recommendations:
- Improve focus ring visibility

### 5) Authentication/state architecture cleanup

Recommendations:
- Keep `App.jsx` focused on route orchestration

### 6) Error handling + resilience

Recommendations:
- Optionally protect async effects against unmounted updates

## Suggested Priority

### High (do first)

1. Login validation + loading state
2. Better error messages by failure type
3. Initial auth-check loading UI

### Medium

1. Responsive login polish
2. Accessibility improvements (labels, autocomplete, aria)
3. Extract `LoginForm` component

### Low / Next phase

1. `useAuth` hook extraction
2. Optional token refresh strategy
3. Error boundary around league-selection path

## Testing Targets

### Unit / component tests
- `LoginForm`:
  - required field validation
  - submit success path
  - submit failure variants

### Hook tests (if extracting `useAuth`)
- logout clears state + storage

### App integration tests
- no league selected → `LeagueSelector` path

## Notes for Future Contributors
- Treat auth/login UX as a critical path: clarity, responsiveness, and error specificity matter.
---

## Draft Value UI & Analysis

New UI components/pages are being added for draft value analysis and player information:

- **Draft Value Analysis Page:** Displays normalized draft value data from ESPN, Yahoo, and Draftsharks APIs. Users can filter by year, position, and team.
- **Player Info Modal/Page:** Shows draft value, projected points, ADP, and position rank for each player, sourced from the new database.
- **Commissioner Tools:** Allows commissioners to review, update, and normalize draft value data for league setup and draft prep.

These features are accessible from the main dashboard, draft board, and commissioner pages.
