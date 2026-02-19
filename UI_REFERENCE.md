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

- Clean top-level routing guard logic
- Consistent `localStorage` usage for token + league context
- Good base dark-theme contrast and visual hierarchy

## High-Impact Improvements

### 1) Login form validation + loading feedback

Problems:

- Empty submit is allowed
- No explicit loading state during auth request
- Generic error feedback

Recommendations:

- Add `isLoading` state and disable inputs/button while submitting
- Validate `username` + `password` before API call
- Distinguish error types (`401`, network, throttling, server)

### 2) Initial auth-check loading state

Problems:

- Potential blank/flicker while `/auth/me` resolves

Recommendations:

- Add `isAuthChecking` state
- Show a small loading shell while token validation is in flight

### 3) Responsive login container

Problems:

- Fixed width patterns are fragile on narrow screens

Recommendations:

- Use fluid width + max-width (`w-full max-w-md` style)
- Keep spacing responsive (`p-6 sm:p-8`)

### 4) Accessibility pass

Recommendations:

- Ensure all form inputs have associated labels (`id` + `htmlFor`)
- Add `autoComplete` for auth fields
- Add `aria-label` on icon-only buttons
- Improve focus ring visibility

### 5) Authentication/state architecture cleanup

Recommendations:

- Extract auth/localStorage behavior into a `useAuth` hook
- Normalize persisted values when reading from storage
- Keep `App.jsx` focused on route orchestration

### 6) Error handling + resilience

Recommendations:

- Gracefully handle 401 globally (logout + redirect)
- Add fallback UX around league-loading flow (`LeagueSelector` errors/retry)
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

- initialize from `localStorage`
- login updates state + storage
- logout clears state + storage

### App integration tests

- token exists → `/auth/me` check runs and app shell renders
- auth failure → logout path + login screen
- no league selected → `LeagueSelector` path

## Notes for Future Contributors

- Keep top-level app flow explicit and easy to read.
- Prefer thin route containers and move logic into focused components/hooks.
- Treat auth/login UX as a critical path: clarity, responsiveness, and error specificity matter.
