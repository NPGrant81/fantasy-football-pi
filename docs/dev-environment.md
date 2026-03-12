# Dev Environment Guide

Date: 2026-03-10
Related Issue: #206

## Git Worktrees (Parallel Dev Workflow)

Use worktrees only when parallel branch development is needed.

### Standard usage
- Keep 2 active worktrees by default:
  - `main`
  - current issue branch

### Create a worktree for an issue
```bash
git fetch origin
git worktree add ../ffpi-issue-73 -b fix/issue-73-site-visit-logging origin/main
```

### List worktrees
```bash
git worktree list
```

### Remove a completed worktree
```bash
git worktree remove ../ffpi-issue-73
git worktree prune
```

### Cleanup routine
- After each merged PR: remove that branch worktree.
- Weekly: run `git worktree list` and prune obsolete entries.

### Safety checks
- Ensure no uncommitted changes before removal:
```bash
git -C ../ffpi-issue-73 status
```

- If a branch is no longer needed after merge:
```bash
git branch -d fix/issue-73-site-visit-logging
git fetch origin --prune
```

## Using Cloudflare Tunnel in VS Code

This workflow uses the VS Code extension:
- Extension ID: `ivanarjona.cloudflaretunnel`
- Marketplace name: `Cloudflare Tunnel`

### 1. Install extension
- Open Extensions in VS Code.
- Search for `Cloudflare Tunnel`.
- Install `ivanarjona.cloudflaretunnel`.

Repo recommendation is preconfigured in `.vscode/extensions.json`.

### 2. Authenticate with Cloudflare
- Open Command Palette (`Ctrl+Shift+P`).
- Run `Cloudflare Tunnel: Login`.
- Complete browser auth flow.
- Return to VS Code and verify extension commands are available.

### 3. Start app services locally
Backend:
```bash
cd backend
python3.13.exe -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload
```

Frontend:
```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

### 4. Create tunnel from VS Code
- Command Palette -> `Cloudflare Tunnel: Create Tunnel` (or equivalent command exposed by the extension).
- For frontend sharing, target `http://127.0.0.1:5173`.
- For backend sharing, target `http://127.0.0.1:8010`.

If extension supports named presets, save two entries:
- `ffpi-frontend-dev` -> `5173`
- `ffpi-backend-dev` -> `8010`

### 5. Validate public URLs
- Open generated HTTPS URL in browser/mobile.
- Frontend URL should render app shell.
- Backend URL health check should respond:
```bash
curl -i https://<backend-tunnel-url>/health
```

### 6. Team demo flow
- Start frontend tunnel and share URL with teammates.
- If API calls fail via public frontend URL, also expose backend and update temporary frontend proxy target for demo session.

## Screenshots checklist
Capture and store screenshots for onboarding updates:
1. Extension installed in VS Code.
2. Command Palette showing `Cloudflare Tunnel` commands.
3. Successful login/auth completion.
4. Running tunnel with public URL visible.

Suggested storage path: `docs/uat/`.

## Troubleshooting
### No Cloudflare Tunnel commands appear
- Reload VS Code window.
- Ensure extension is enabled in current workspace.

### Login command fails
- Retry `Cloudflare Tunnel: Login`.
- Confirm browser opens and Cloudflare auth completes.
- Check firewall/VPN restrictions.

### Tunnel URL opens but app fails
- Verify local service is actually running on the selected port.
- Verify backend is on `8010` and frontend on `5173`.
- Check terminal logs for local server errors.

### Frontend loads but API calls fail
- Ensure backend tunnel is also running.
- Confirm frontend proxy target points to accessible backend URL.

## Notes
- This VS Code extension workflow is for day-to-day dev convenience.
- For persistent Raspberry Pi production tunnels, use:
  - `docs/cloudflare-tunnel-cli.md`
  - `docs/cloudflare-tunnel-systemd.md`
