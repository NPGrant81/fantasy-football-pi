### Gap 09 — Architecture Decision Records (ADR System)

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Labels:** `documentation`, `architecture`, `adr`

---

**Summary**

Establish a lightweight Architecture Decision Record (ADR) system to capture and preserve the reasoning behind key technical decisions. ADRs prevent decision revisitation, onboard new contributors faster, and provide an audit trail for deferred or deprecated choices.

Currently there is no ADR template, no index, and no recorded decisions.

---

**Tasks**

- [ ] Create `docs/adr/README.md` — ADR index listing all records with title, status (`Proposed` / `Accepted` / `Deprecated` / `Superseded`), and date
- [ ] Create `docs/adr/adr-000-template.md` — standard ADR template with sections: Title, Status, Context, Decision, Consequences
- [ ] Write `docs/adr/adr-001-containerization-strategy.md` — Docker vs bare-metal deployment decision
- [ ] Write `docs/adr/adr-002-reverse-proxy.md` — Nginx as reverse proxy vs alternatives (Caddy, Traefik)
- [ ] Write `docs/adr/adr-003-database-engine.md` — SQLite vs PostgreSQL for production on Pi hardware
- [ ] Write `docs/adr/adr-004-service-architecture.md` — Monolith vs microservices for current team size and scope
- [ ] Update `docs/adr/README.md` index when any new ADR is added
- [ ] Add a note to `CONTRIBUTING.md` that significant architectural changes require a new or updated ADR

---

**Acceptance Criteria**

- `docs/adr/` directory exists with a `README.md` index and `adr-000-template.md`
- At least four ADRs are written and in `Accepted` status (containerization, reverse proxy, database, architecture)
- Each ADR follows the standard template format
- `CONTRIBUTING.md` references the ADR process for architectural changes
- The ADR index is kept up-to-date as new records are added
