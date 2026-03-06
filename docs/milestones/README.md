# Project Milestones

This directory contains the milestone definitions for the fantasy‑football platform roadmap. Each file describes one milestone's scope, completion criteria, child issues, and dependencies.

---

## Milestone Overview

| # | Milestone | Status | Description |
|---|-----------|--------|-------------|
| 1 | [Core Application Foundation](milestone-1-core-foundation.md) | 🔄 In Progress | Backend, frontend, DB schema |
| 2 | [Cross‑Platform Compatibility & Deployment](milestone-2-cross-platform-deployment.md) | ⏳ Planned | Windows + Pi parity, CI pipeline |
| 3 | [Security Hardening](milestone-3-security-hardening.md) | ⏳ Planned | Auth, CSRF, CSP, infrastructure |
| 4 | [Data‑Validation Architecture](milestone-4-data-validation.md) | ⏳ Planned | Pydantic, Cerberus, Marshmallow, Pandera, GE |
| 5 | [Gameplay Logic & League Operations](milestone-5-gameplay-logic.md) | 🔄 In Progress | Roster rules, scoring, matchups |
| 6 | [Production Readiness & Monitoring](milestone-6-production-readiness.md) | ⏳ Planned | Logging, backups, monitoring |
| 7 | [Release 1.0](milestone-7-release-1.0.md) | ⏳ Planned | QA, docs, version tag |

---

## Dependency Chain

```
Milestone 1 (Core Foundation)
    ├── Milestone 2 (Cross‑Platform + CI)
    │       └── Milestone 3 (Security)
    │               └── Milestone 5 (Gameplay)
    │                       └── Milestone 6 (Production)
    └── Milestone 4 (Data Validation) ──┘
                                         └── Milestone 7 (Release 1.0)
```

---

## Related Documents

- [PROJECT_MANAGEMENT.md](../PROJECT_MANAGEMENT.md) — Story numbering, sprint recommendations
- [ARCHITECTURE.md](../ARCHITECTURE.md) — System architecture overview
- [SECURITY_HARDENING.md](../SECURITY_HARDENING.md) — Security baseline decisions
- [issues/](../../issues/) — Individual issue tracking files
