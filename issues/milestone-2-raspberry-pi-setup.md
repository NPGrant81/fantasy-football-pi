### Issue 5 — Raspberry Pi Deployment Setup (Phase 1: Raspberry Pi OS Setup)

**GitHub Issue:** #81  
**Milestone:** Milestone 2 — Raspberry Pi Deployment Setup  
**Labels:** `devops`

---

**Summary**

Prepare a Raspberry Pi 5 as a headless Linux host for the project, including imaging, first boot, SSH access, and the baseline decisions needed before app deployment.

---

**Tasks**

- [x] Add a runbook section for Raspberry Pi Imager configuration
- [x] Document first-boot workflow and SSH login path
- [x] Document hostname/IP fallback guidance for headless access
- [x] Document immediate post-boot validation commands
- [x] Record pre-deployment inputs needed before Nginx/systemd/TLS work
- [x] Draft implementation summary and verification notes for GitHub issue #81 close-out

---

**Acceptance Criteria**

- A fresh Raspberry Pi can be imaged with Raspberry Pi OS Lite (64-bit) using documented settings.
- The host can be reached over SSH after first boot without local peripherals.
- The runbook documents the exact transition from first boot into later deployment phases.
- Later deployment work such as Nginx, systemd, Cloudflare, and TLS remains clearly separated from Phase 1.

---

**Repo implementation**

- Primary runbook: `docs/RASPBERRY_PI_DEPLOYMENT.md`
- Related follow-on issue: `issues/pre-deploy-raspberry-pi-host-foundation-checklist.md`

---

**Close-out draft**

- Close-out notes: `docs/PR_NOTES.md` under `Issue #81 Close-Out Notes`
- Closure queue entry: `docs/ISSUE_STATUS.md`
