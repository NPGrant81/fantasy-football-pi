### Issue 4 — Cross‑Platform Path Handling

**Milestone:** [Milestone 2 — Cross‑Platform Compatibility & Deployment](../docs/milestones/milestone-2-cross-platform-deployment.md)  
**Labels:** `cross-platform`, `backend`, `tech-debt`

---

**Context update (2026-03-19)**

Development environment moved from Windows to Linux (Raspberry Pi / PPL Insight Hub machine). Primary
deployment target remains Raspberry Pi (Linux). Windows is no longer the active dev surface.
Cross-platform scope has been refined: the goal is now Linux ↔ Linux (dev ↔ Pi) parity, with enough
CI coverage to catch any Windows-specific code introduced if development ever returns to Windows.

---

**Summary**

Ensure all file paths and OS interactions use cross‑platform safe methods. Add CI coverage to detect
platform-specific regressions on both Linux and Windows.

---

**Tasks**

- [x] Audit codebase for Windows-specific path patterns (2026-03-19)
- [x] Fix `backend/routers/etl.py`: replace hardcoded `"python"` subprocess call with `sys.executable`
- [x] Fix `backend/scripts/debug_import.py`: replace `.replace('\\', '/')` SQLite workaround with `Path.as_posix()`
- [x] Fix `backend/tests/test_scoring_import.py`: same `.replace('\\', '/')` workaround replaced with `Path.as_posix()`
- [x] Add `.github/workflows/cross-platform-compat.yml`: OS matrix (ubuntu-latest + windows-latest) running lint + import smoke test + SQLite-safe test subset
- [x] Run Linux baseline: 254 pass, 4 fail, 1 skip (failures are Postgres-specific or existing logic bugs — not platform regressions)
- [ ] Replace remaining `os.path.join` usage in scripts with `pathlib.Path` (low risk but improves readability)
- [ ] Standardize `backend/alembic/env.py` path construction to use `pathlib`

**De-scoped:**
- Windows CI runner with full Postgres test suite — not viable (Docker service containers unsupported on `windows-latest`). The `cross-platform-compat.yml` SQLite-safe matrix covers import/syntax/logic validation on Windows.

---

**Acceptance Criteria**

- [x] Code imports cleanly on both Linux and Windows (verified via cross-platform-compat CI job)
- [x] No hardcoded `"python"` subprocess invocations (use `sys.executable`)
- [x] No `.replace('\\', '/')` workarounds in path-to-URL conversions (use `Path.as_posix()`)
- [ ] No remaining `os.path.join` in scripts (stretch goal — low risk)
- [x] CI matrix runs on push/PR and reports parity between both OSes
