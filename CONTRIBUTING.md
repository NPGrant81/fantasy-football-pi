# Contributing to Fantasy Football PI

Thank you for your interest in contributing! This project follows a strict
"Debug‑First" workflow to keep the frontend maintainable and prevent
"works on my machine" bugs. Please read the sections below before opening a
PR.

---

## Frontend Verification & Debugging Standards

To ensure data integrity and system reliability, all frontend development
must follow the **Debug‑First protocol**. "It works on my screen" is not a
sufficient test.

1. **Mandatory Breakpoint Audit**
   - Every new or modified `.jsx` module must be verified using the VS Code
     Debugger (not just console.log). You must explicitly inspect three
     lifecycle stages of the component:
     1. **The Data Fetch (Entry):** Place a breakpoint at the start of every
        `useEffect` or custom hook that initiates an API call. Verify that
        parameters (like `leagueId` or `token`) are valid and not `undefined`
        before the request is fired.
     2. **The Transformation (Data Receipt):** Place a breakpoint immediately
        after an `await apiClient...` call or inside a `.then()` handler. In
        the _Variables_ pane, inspect the raw `response.data` and confirm its
        shape matches what the component expects (e.g. `is_taxi` is a
        boolean, not a string).
     3. **The User Action (Handler):** Place a breakpoint on the first line of
        any `handle*` function (e.g. `handleSubmit`, `handleTaxiMove`).
        Before the payload is sent, verify local state to ensure every field is
        correct.

2. **Naming & Case Sensitivity**
   - The codebase uses **PascalCase** for all React component file names
     (e.g. `ManageCommissioners.jsx`).
   - Never commit two files whose names differ only by case (e.g.,
     `manage-commissioners.jsx` vs. `ManageCommissioners.jsx`). This causes
     module resolution failures in CI/CD and production (Netlify, Vercel,
     etc.).
   - Before committing, run `git ls-files` or inspect your editor to ensure the
     file names exactly match their exported component names.

3. **Definition of Done (DoD)**
   A feature is not considered complete until all three of the following are
   satisfied:
   - ✅ **Test Pass:** `npm run test` (Vitest) completes with zero regressions.
   - ✅ **Debug Pass:** The developer has walked through the component
     lifecycle using the "Frontend: Chrome" VS Code launch config (see below)
     and verified state changes with at least one of the three required
     breakpoints.
   - ✅ **Clean Console:** No warnings about missing `key` props, unhandled
     promise rejections, or hydration errors appear in the browser console.

---

## Debugger Setup (VS Code)

Add the following section to `.vscode/launch.json` (or merge it into your
existing configuration) so you can step through the frontend code in Chrome:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Frontend: Chrome",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/frontend",
      "sourceMapPathOverrides": {
        "webpack:///src/*": "${webRoot}/src/*"
      }
    }
  ]
}
```

Start the Vite dev server (`npm run dev`) and then launch this configuration to
hit breakpoints as you interact with the UI.

---

## Current Action Items

1. **Maintain naming and structure hygiene.**
   - Keep React component filenames in PascalCase and avoid case-only name
     differences in tracked files.
   - If you add a new route page or major module, place it under the existing
     feature folders (for example `src/pages/commissioner/`) rather than
     introducing ad-hoc top-level folders.

2. **Audit critical pages.**
   - Before adding new UI (e.g. Taxi Squad) or touching existing logic
     (LineupRules, WaiverRules, etc.), set breakpoints in each module’s
     fetch hooks and handlers as described above and walk through them using
     the VS Code debugger. Capture a screenshot of the _Variables_ pane for
     at least one component to prove the audit was done.

3. **Keep docs and route matrices synchronized.**
   - Any new page, endpoint surface, or major integration should be reflected
     in `docs/API_PAGE_MATRIX.md` and linked from `docs/INDEX.md`.
   - If docs in `docs/` change, ensure index updates are included in the same
     PR.

4. **Follow the DoD on every PR.** Any pull request lacking one of the three
   DoD checks (tests, debugger walkthrough, clean console) should be
   rejected until the developer demonstrates compliance.

---

By adhering to these standards, the frontend stops being a black box and
becomes a maintainable, predictable codebase. Thank you for taking this
extra step! 👏
