# Milestone 2 — Cross‑Platform Compatibility & Deployment Pipeline

This milestone ensures the project runs identically on Windows and Raspberry Pi, with a clean deployment workflow.

---

## Scope

- Cross‑platform path handling using `pathlib`
- ARM‑compatible dependency verification
- Raspberry Pi setup (Python, Node, Nginx, systemd)
- Deployment scripts or documentation
- GitHub Actions for linting, type checking, and dependency scanning

---

## Completion Criteria

- [ ] Code deploys cleanly to Raspberry Pi
- [ ] Backend runs under systemd
- [ ] Nginx serves frontend and proxies backend
- [ ] CI validates cross‑platform compatibility

---

## Child Issues

| Issue | Title | Labels |
|-------|-------|--------|
| [Issue 4](../../issues/milestone-2-cross-platform-paths.md) | Cross‑Platform Path Handling | `cross-platform`, `backend`, `tech-debt` |
| [Issue 5](../../issues/milestone-2-raspberry-pi-setup.md) | Raspberry Pi Deployment Setup | `deployment`, `infrastructure`, `raspberry-pi` |
| [Issue 6](../../issues/milestone-2-ci-pipeline.md) | CI Pipeline Setup | `ci/cd`, `security`, `automation` |

---

## Dependencies

- Milestone 1 — Core Application Foundation must be complete.

---

## Notes

See [deploy/](../../deploy/) for existing deployment scripts and [docs/ARCHITECTURE.md](../ARCHITECTURE.md) for infrastructure details.
