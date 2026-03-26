### Issue #298 — Raspberry Pi Production Cutover Readiness

**Milestones:**
- [Milestone 2 — Cross-Platform Compatibility & Deployment](../docs/milestones/milestone-2-cross-platform-deployment.md)
- [Milestone 3 — Security Hardening](../docs/milestones/milestone-3-security-hardening.md)
- [Milestone 6 — Production Readiness & Monitoring](../docs/milestones/milestone-6-production-readiness.md)
- [Milestone 7 — Release 1.0](../docs/milestones/milestone-7-release-1.0.md)

**Suggested Labels:** `deployment`, `infrastructure`, `raspberry-pi`, `cloudflare`, `monitoring`, `security`

**GitHub Issue:** https://github.com/NPGrant81/fantasy-football-pi/issues/298

---

**Summary**

Baseline Raspberry Pi host preparation is complete, but the production app cutover is still not fully closed. This issue tracks the remaining Raspberry Pi work required to make the app deployment-ready, publicly reachable through Cloudflare Tunnel, operationally recoverable, and ready for release deployment.

This issue is intended to consolidate the remaining app-coupled Pi work that is currently split across deployment, security, monitoring, and release milestones.

**Execution Cadence Update (2026-03-20)**

- Backend setup and production cadence execution are in progress on branch `chore/cloudflare-phase3-followup`.
- Current cadence focus: backend systemd enablement, nginx app routing verification, cloudflared recovery, and timer activation.
- Next checkpoint: publish gate-by-gate evidence for local-origin validation, public tunnel validation, and reboot resilience.

---

**Related Existing Issues**

- `#290` — Pre-Deploy Raspberry Pi Host Foundation Checklist (baseline host prep complete)
- `#83` — Phase 3: Secure Connection (Cloudflare Tunnel)
- `#79` — Unified Architecture, Security, and Cross-Platform Development Strategy
- `#17` — Monitoring & Backups

---

**Tasks**

- [ ] Finalize backend production environment values on the Pi
  - [ ] Set production secrets and runtime env file under `/etc/fantasy-football-pi/backend.env`
  - [ ] Finalize `ALLOWED_HOSTS`
  - [ ] Finalize `FRONTEND_ALLOWED_ORIGINS`
  - [ ] Verify backend starts cleanly under systemd with production env applied

- [ ] Complete final Nginx app wiring on the Pi
  - [ ] Install the final app site config from `deploy/nginx/fantasy-football-pi.conf.example`
  - [ ] Verify frontend static serving from `/var/www/fantasy-football-pi/frontend/dist/`
  - [ ] Verify reverse proxy routing for backend paths
  - [ ] Run `nginx -t` and reload successfully

- [ ] Verify local-origin production behavior before public cutover
  - [ ] `curl -fsS http://127.0.0.1:8000/health`
  - [ ] `curl -I http://127.0.0.1/`
  - [ ] `curl -I http://127.0.0.1/auth/me`
  - [ ] Confirm `fantasy-football-backend.service` is enabled and active
  - [ ] Confirm `nginx.service` is enabled and active

- [ ] Activate backups against the final database target
  - [ ] Install/copy the final backup script and related systemd units
  - [ ] Enable the backup timer on the Pi
  - [ ] Confirm timer scheduling with `systemctl list-timers`
  - [ ] Execute at least one backup run successfully
  - [ ] Validate restore from produced backup artifacts

- [ ] Complete Cloudflare Tunnel production cutover
  - [ ] Install `cloudflared` on the Pi if not already present
  - [ ] Stage `/etc/cloudflared/config.yml`
  - [ ] Place the named-tunnel credentials JSON in `/etc/cloudflared/`
  - [ ] Enable and verify `cloudflared.service`
  - [ ] Enable and verify `cloudflared-watchdog.timer`
  - [ ] Map `pplinsighthub.com` and `www.pplinsighthub.com` to the named tunnel
  - [ ] Verify public root page, `/auth/me`, and `/health` through Cloudflare

- [ ] Close the remaining Pi security hardening gaps
  - [ ] Confirm SSH key-based authentication is enabled
  - [ ] Confirm password SSH login is disabled
  - [ ] Verify firewall rules expose only intended ports/services
  - [ ] Confirm HTTPS/HSTS posture for the public edge design in use
  - [ ] Verify fail2ban remains enabled and healthy after final service wiring

- [ ] Complete Pi monitoring and alerting baseline
  - [ ] Confirm structured backend logs are observable
  - [ ] Add lightweight system monitoring for CPU, memory, and traffic anomalies
  - [ ] Configure alerting for critical tunnel, backend, or host failures
  - [ ] Document incident response steps for common Pi production failures

- [ ] Reboot and recovery validation
  - [ ] Reboot the Pi and confirm backend, Nginx, cloudflared, watchdog, and backup timer recover automatically
  - [ ] Validate public reachability after reboot
  - [ ] Validate journal visibility for tunnel and backend services after reboot

- [ ] Release and closure follow-through
  - [ ] Reconcile stale milestone checklists that still show Raspberry Pi deployment as incomplete
  - [ ] Confirm code deploys cleanly to Raspberry Pi end-to-end
  - [ ] Tag the release only after Pi deployment verification is complete

---

**Acceptance Criteria**

- Raspberry Pi serves the frontend locally through Nginx and proxies backend routes correctly.
- FastAPI backend runs under systemd with finalized production environment values.
- Cloudflare Tunnel is configured with production credentials and serves the public hostnames successfully.
- Backup automation is enabled against the real database target and a restore test has been completed.
- SSH, firewall, and service hardening checks are verified on the final Pi deployment.
- Monitoring and alerting are sufficient to detect app, tunnel, or host failures within minutes.
- Reboot validation confirms all critical services recover automatically.
- Deployment documentation and milestone tracking are aligned with the final operational state.

---

**Primary References**

- `docs/RASPBERRY_PI_DEPLOYMENT.md`
- `docs/CLOUDFLARE_TUNNEL_SETUP.md`
- `docs/cloudflare-tunnel-monitoring.md`
- `docs/PI_UPDATE_CHEATSHEET.md`
- `docs/PR_NOTES.md`

---

**Suggested GitHub Issue Body**

```md
Baseline Raspberry Pi host preparation is complete, but the production app cutover is still not fully closed. This issue tracks the remaining Raspberry Pi work required to make the app deployment-ready, publicly reachable through Cloudflare Tunnel, operationally recoverable, and ready for release deployment.

Related issues:
- #290 — baseline host prep
- #83 — Cloudflare Tunnel cutover
- #79 — architecture/security umbrella
- #17 — monitoring and backups

Tasks:
- [ ] Finalize backend production env/secrets on the Pi
- [ ] Complete final Nginx app wiring and local-origin verification
- [ ] Activate backups against the final database target and verify restore
- [ ] Complete Cloudflare Tunnel production credential placement and cutover
- [ ] Close remaining Pi security hardening gaps
- [ ] Complete monitoring/alerting baseline
- [ ] Perform reboot and recovery validation
- [ ] Reconcile milestone tracking and release deployment closure

Acceptance criteria:
- Pi serves frontend locally through Nginx and proxies backend correctly
- Backend runs under systemd with finalized production env
- Cloudflare Tunnel serves public hostnames successfully
- Backups are automated and restore-tested
- Security hardening checks are verified on the final deployment
- Monitoring can detect app/tunnel/host failures within minutes
- Critical services recover automatically after reboot
```