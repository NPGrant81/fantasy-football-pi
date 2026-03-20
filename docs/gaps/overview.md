# Gap Analysis: Missing Components for Production-Grade Pi Deployment

**Parent Issue:** Gap Analysis & Missing Components for Production‑Grade Pi Deployment  
**Status:** In Progress

---

## Overview

This document summarizes the gaps identified during architecture and deployment planning for the fantasy-football platform on Raspberry Pi OS. Each gap area has a corresponding sub-issue in the `/issues/` directory with detailed tasks and acceptance criteria.

The platform has a strong foundation (Dockerization, systemd, Nginx, dead-code detection, architecture clarification), but several critical production-grade layers remain unimplemented.

---

## Gap Summary Table

| # | Area | Sub-Issue | Priority | Status |
|---|------|-----------|----------|--------|
| 1 | CI/CD Pipeline for ARM64 Builds | [gap-01-ci-cd-arm64.md](../../issues/gap-01-ci-cd-arm64.md) | High | Open |
| 2 | Secrets Management | [gap-02-secrets-management.md](../../issues/gap-02-secrets-management.md) | High | Open |
| 3 | Logging & Monitoring Stack | [gap-03-logging-monitoring.md](../../issues/gap-03-logging-monitoring.md) | Medium | Open |
| 4 | Database Strategy & Backup Plan | [gap-04-database-strategy.md](../../issues/gap-04-database-strategy.md) | High | Open |
| 5 | Automated Test Suite | [gap-05-automated-test-suite.md](../../issues/gap-05-automated-test-suite.md) | High | Open |
| 6 | API Documentation & Schema Validation | [gap-06-api-documentation.md](../../issues/gap-06-api-documentation.md) | Medium | Open |
| 7 | Deployment Automation | [gap-07-deployment-automation.md](../../issues/gap-07-deployment-automation.md) | Medium | Open |
| 8 | Security Hardening | [gap-08-security-hardening.md](../../issues/gap-08-security-hardening.md) | High | Open |
| 9 | Architecture Decision Records (ADR System) | [gap-09-adr-system.md](../../issues/gap-09-adr-system.md) | Low | Open |
| 10 | Performance & Load Testing | [gap-10-performance-load-testing.md](../../issues/gap-10-performance-load-testing.md) | Low | Open |

---

## Gap Descriptions

### 1. CI/CD Pipeline for ARM64 Builds

Multi-architecture Docker builds using `buildx`, automated tagging and publishing to GHCR, and a deployment workflow targeting the Raspberry Pi. Currently, builds are not validated for ARM64 compatibility and there is no automated publish pipeline.

### 2. Secrets Management

Secure handling of credentials, API keys, and TLS material across local development, CI, and production. Includes `.env` templates, GitHub Actions secrets configuration, and Pi-side secure storage conventions.

### 3. Logging & Monitoring Stack

Centralized log aggregation (Loki + Promtail) and optional metrics/dashboards (Grafana, Prometheus). Nginx access and error logs need to be ingested. Health dashboards need to surface app and Pi-level metrics.

### 4. Database Strategy & Backup Plan

Decision between SQLite and PostgreSQL, volume mount strategy for Docker, and an automated backup/restore workflow including off-device backup (OneDrive, S3, or equivalent).

### 5. Automated Test Suite

pytest unit tests, API + DB integration tests, coverage thresholds, and CI test runner integration. Frontend tests are optional but desirable for critical flows.

### 6. API Documentation & Schema Validation

OpenAPI schema generation, Pydantic model alignment, an enabled `/docs` endpoint, and a versioning strategy for API contracts.

### 7. Deployment Automation

A `Makefile` or Bash deploy script supporting zero-downtime deploys, log tailing, and service restart helpers. Reduces manual steps and error-prone SSH commands.

### 8. Security Hardening

UFW firewall rules, Fail2ban configuration, SSH hardening, Nginx security headers, and Docker security best practices applied to the production environment.

### 9. Architecture Decision Records (ADR System)

An ADR template, a populated ADR index, and documented records for key decisions: Docker vs bare-metal, Nginx vs alternatives, SQLite vs PostgreSQL, and monolith vs microservices.

### 10. Performance & Load Testing

Baseline performance metrics, load testing with Locust or k6, and defined regression thresholds to prevent performance degradation across releases.

---

## Acceptance Criteria (Meta-Issue)

- [ ] All 10 gap areas have their own GitHub issues with tasks and acceptance criteria
- [ ] Documentation exists for each area (CI/CD, secrets, DB, security, etc.)
- [ ] The project has a clear roadmap to full production readiness
- [ ] All gaps are resolved or explicitly deferred with ADR justification

---

*This document is maintained alongside the `/issues/gap-*.md` files. Update the Status column as sub-issues are resolved.*
