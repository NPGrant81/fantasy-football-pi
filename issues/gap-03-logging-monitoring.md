### Gap 03 — Logging & Monitoring Stack

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Labels:** `observability`, `logging`, `monitoring`, `infrastructure`

---

**Summary**

Deploy a centralized logging and monitoring stack on the Raspberry Pi so that application, Nginx, and system-level events can be queried and visualized. The stack should be lightweight enough to run alongside the application on Pi hardware.

Currently there is no log aggregation, no health dashboard, and no alerting.

---

**Tasks**

- [ ] Evaluate lightweight observability stack for ARM64 (Loki + Promtail + Grafana recommended; assess RAM/CPU feasibility on Pi)
- [ ] Add `docker-compose.monitoring.yml` (or extend main compose file) with Loki, Promtail, and Grafana services
- [ ] Configure Promtail to ingest: application container logs, Nginx access/error logs, and systemd journal
- [ ] Create a Grafana dashboard for: request rate, error rate, response latency, and Pi system metrics (CPU, RAM, disk)
- [ ] Add a `/health` endpoint to the FastAPI backend (if not already present) returning `200 OK` with service status
- [ ] Configure Grafana alerting (or Prometheus Alertmanager) for: high error rate, disk > 80%, service down
- [ ] Document stack setup and dashboard import in `docs/MONITORING.md`

---

**Acceptance Criteria**

- Loki + Promtail + Grafana run on the Pi without exceeding 512 MB additional RAM under normal load
- Nginx and application logs are visible and queryable in Grafana within 60 seconds of generation
- At least one dashboard exists covering request rate, error rate, and latency
- Pi system metrics (CPU, RAM, disk) are visible in Grafana
- `/health` endpoint returns `200 OK` when all dependencies are healthy
- Alerts fire within 5 minutes of a monitored threshold being exceeded
- Setup and dashboard import documented in `docs/MONITORING.md`
