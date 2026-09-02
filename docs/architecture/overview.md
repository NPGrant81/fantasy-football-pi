# System Topology Authority

- Status: canonical
- Owner: engineering
- Last reviewed: 2026-08-31
- Review cadence: 90 days
- Supersedes: prior topology guidance in `docs/ARCHITECTURE.md` and the former `docs/architecture-overview.md` architecture summary
- Originating decision: Issue #302 (2026-03-21)

## Authority and Scope

This document is the canonical authority for the as-built system topology,
deployment units, service boundaries, and microservice decomposition triggers.
For code placement and dependency direction inside those units, defer to
`docs/ARCHITECTURE.md`.

## Status

- Current architecture: modular monolith
- Container tooling: supported packaging and orchestration, not a service boundary

## Short Answer

The platform is a modular monolith, not a microservice architecture. Its
service-oriented backend modules remain in one backend deployment boundary.

## Current Architecture (As Built)

- **Development:** Vite serves the frontend on `127.0.0.1:5173`; Docker Compose
    supplies PostgreSQL on `5432` and an optional Redis instance on `6379`.
- **Production:** a Raspberry Pi runs FastAPI/Uvicorn as a systemd service on
    `127.0.0.1:8000`, native PostgreSQL, and Nginx for static delivery and API
    reverse proxying. The backend unit applies migrations through `ExecStartPre`
    before Uvicorn starts.
- Cloudflare Tunnel reaches Nginx on the Pi; Nginx is the single ingress owner
    for the frontend and backend route families.
- Redis is optional infrastructure for the distributed rate limiter. Production
    defaults to the in-memory limiter unless `RATE_LIMITER_BACKEND=redis` is
    deliberately configured.

```mermaid
flowchart LR
        User[User browser]

        subgraph Production[Production Raspberry Pi]
                Tunnel[Cloudflare Tunnel]
                Nginx[Nginx]
                Static[React static files]
                Api[FastAPI Uvicorn :8000]
                Database[(Native PostgreSQL)]
        end

        subgraph Development[Development workstation]
                Vite[Vite React :5173]
                Compose[Docker Compose]
                DevDatabase[(PostgreSQL :5432)]
                Redis[Redis :6379 optional]
        end

        User --> Tunnel
        Tunnel --> Nginx
        Nginx --> Static
        Nginx --> Api
        Api --> Database
        Vite --> Api
        Compose --> DevDatabase
        Compose --> Redis
```

The source for this diagram is `docs/diagrams/system-topology.mmd`.

## Containerized vs Microservices

Containerized describes runtime packaging and orchestration. It does not define
the application architecture, and supported launchers may run components without
making each component an independent service.

Microserviced means the system is split into independent services that have:

- independent deployability
- independent scaling
- independent failure domains
- explicit API contracts between services
- service-level ownership and lifecycle boundaries

Our current stack does not yet meet these microservice criteria.

## Natural Service Boundaries (If We Evolve Later)

Potential candidates if future scale or team topology requires decomposition:

- data ingestion/sync pipelines
- scoring and simulation compute workloads
- notifications/reporting delivery

These are not separate services today. They remain modules inside the backend codebase.

## Decision

For near-term delivery, the project remains a modular monolith. Container tooling
may package and orchestrate its runtime units without changing that topology.

Rationale:

- lower operational complexity for a small team
- simpler local development and deployment
- fewer network and observability failure points
- easier transactional consistency while core features stabilize

## Revisit Triggers

Revisit microservice decomposition when one or more signals are sustained:

- backend module release cadence causes cross-team blocking
- specific workloads require independent horizontal scaling
- uptime requirements need stricter service isolation
- deployment blast radius becomes operationally expensive

## Decision Matrix (Operational Revisit Rubric)

Use this matrix after production launch to decide whether to keep the modular monolith or split a service boundary.

| Signal | Measure | Keep Monolith Guidance | Split Candidate Guidance |
| --- | --- | --- | --- |
| Team ownership contention | Number of blocked releases per month due to unrelated backend changes | 0-1 blocked releases/month | 3+ blocked releases/month for 2+ consecutive months |
| Independent scaling need | Ratio between peak-heavy workload demand and baseline API demand | Less than 2x | Greater than or equal to 4x and recurring weekly |
| Reliability isolation pressure | Incidents where one subsystem degraded unrelated user paths | 0-1 incident/quarter | 2+ incidents/quarter tied to same subsystem |
| Deploy blast radius | Percentage of deploys requiring full backend rollout for local changes | Less than 50% | Greater than or equal to 80% for 2+ consecutive sprints |
| Recovery speed pressure | Mean time to recover (MTTR) for subsystem failures | Less than 30 minutes | Greater than 60 minutes where isolation would reduce impact |
| Data consistency complexity | Cross-domain transactions needing strict ACID in one request | Frequent and core to user paths | Mostly asynchronous/event-friendly workflows |

Interpretation:

- If 0-1 split indicators are true, continue as modular monolith.
- If 2 indicators are true for 2+ review cycles, run a design spike for one service extraction.
- If 3+ indicators are true for 2+ review cycles, prioritize extracting the highest-impact boundary.

## Revisit Cadence

Run a formal architecture review at the following checkpoints:

- 30 days after production go-live
- 90 days after production go-live
- quarterly thereafter

For each review, capture:

- current metric values for each matrix signal
- whether each signal is monolith-favoring or split-favoring
- recommendation for the next quarter (stay monolith, design spike, or extract one service)

## Recommended First Extraction Order (If Triggered)

If the matrix indicates a split, extract one boundary at a time in this order:

1. ingestion/sync pipelines
2. scoring and simulation compute workloads
3. notifications/reporting delivery

This ordering minimizes user-facing risk by separating the most batch-oriented or compute-heavy responsibilities first.
