# Responsive Breakpoint Audit by Environment

Use this guide when running the responsive breakpoint audit locally.

Audit script:
- `audit-breakpoints.sh`

## Linux / Raspberry Pi

Raspberry Pi OS and other Linux environments include `bash` by default.

```bash
cd frontend
bash ../audit-breakpoints.sh
```

## Windows (PowerShell)

PowerShell alone may not have `bash` on PATH. Use one of these options:

1. Git Bash terminal
2. WSL terminal
3. PowerShell wrapper script from repo root

```powershell
.\scripts\run_repo_hygiene.ps1
```

If you specifically want to run the responsive audit script itself from PowerShell,
run it through an installed bash environment (Git Bash or WSL).

## CI behavior

CI executes the responsive audit in a Linux runner via:
- `.github/workflows/ci.yml`

So local Windows failures like `bash: ... not recognized` are environment/tooling
issues, not audit-rule issues.

## Wrapper Components and Opt-out

Some files are compatibility wrappers with no layout classes (for example
`MyTeam.jsx` re-export wrappers). Those files can opt out of the breakpoint check
with this comment in the file:

```jsx
/* ignore-breakpoints */
```

Use this only when the file truly has no responsive UI responsibilities.
