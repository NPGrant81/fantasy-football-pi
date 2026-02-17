UI Evaluation Notes — `App.jsx`
--------------------------------

Quick observations
- `App.jsx` handles three primary paths: Not authenticated (login), authenticated but no league (LeagueSelector), and full app (Layout + Routes).
- It stores `token`, `activeLeagueId`, and `user_id` in `localStorage` and uses `apiClient` to validate the token on mount.

Suggested improvements
- Move localStorage access into a small `useAuth` hook to centralize persistence and side-effects. This simplifies testing and component logic.
- Make `apiClient.get('/auth/me')` cancelable or check mounted state before updating state to avoid memory leaks if component unmounts during network calls.
- Add explicit loading state for the initial auth check to avoid flashing UI.
- Extract the login form into `LoginForm` component for isolation and unit testing (handleLogin can be injected via props).
- Persist boolean types and ids consistently (parse `localStorage` values) to avoid truthiness bugs.

Targeted tests to add
- `LoginForm` unit tests: form validation, `handleLogin` success & failure flows (mock `apiClient.post`).
- `useAuth` hook tests: initialization from `localStorage`, login updates, logout clears storage.
- `App` integration test: simulate token present and verify `apiClient.get('/auth/me')` is called and Layout is rendered.

Accessibility & UX
- Ensure the login inputs have associated `label` elements with `htmlFor` and `id` attributes for better accessibility.
- Button elements that only contain icons (e.g., advisor send button) should include `aria-label` attributes.

Performance
- Debounce expensive operations (if any future search features are added to `LeagueAdvisor`).
