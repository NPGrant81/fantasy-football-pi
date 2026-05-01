---
name: project-bootstrap
description: 'Fantasy Football PI dev environment setup, first-run configuration, environment variables, Docker, virtual environments, and onboarding new contributors. Use when: setting up a dev machine, onboarding, configuring .env, starting services, or troubleshooting startup failures.'
argument-hint: 'Optional: specify what part of setup you need (backend | frontend | database | all)'
---

# Project Bootstrap

## Why This Exists
Fantasy Football PI runs on a Raspberry Pi in production with Cloudflare Tunnel + Nginx. The dev environment closely mirrors production but uses Docker for the database. New contributors need a deterministic setup sequence to avoid environment drift.

## Stack at a Glance
| Layer | Tech |
|-------|------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy (sync + async patterns), Alembic |
| Frontend | React 18, Vite, TypeScript/JSX, Tailwind CSS, Vitest |
| Database | PostgreSQL (Docker in dev, native on Pi in prod) |
| Infra | Raspberry Pi 4, Nginx, Cloudflare Tunnel, systemd |

## Setup Sequence

### 1. Clone & Environment File
```bash
git clone https://github.com/NPGrant81/fantasy-football-pi.git
cd fantasy-football-pi
cp .env.example .env   # then fill in values
```
Required `.env` keys: `DATABASE_URL`, `SECRET_KEY`, `MFL_API_KEY`, `ESPN_S2`, `ESPN_SWID`, `LEAGUE_ID`

### 2. Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Database
```bash
# Start PostgreSQL via Docker
docker-compose up -d db

# Run migrations
alembic upgrade head

# (Optional) seed reference data
python scripts/seed_data.py
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 5. Start Dev Servers
```bash
# From repo root — starts both backend and frontend
./start-dev.sh    # Linux/Mac
# or
./start-dev.ps1   # PowerShell
```

## Always Do
- Activate the virtualenv before running any backend command
- Run `alembic upgrade head` after pulling changes that touch `models.py`
- Use `docker-compose` for the local database; do not install PostgreSQL manually on dev machines
- Check `requirements.txt` vs `requirements-lock.txt` — lock file pins exact versions for reproducibility
- Set `PYTHONPATH=backend` when running pytest from the repo root

## Never Do
- Never commit `.env` or any file containing secrets
- Never run `npm install` inside `backend/`
- Never modify `alembic/env.py` unless explicitly required — migrations break
- Never use `pip install <package>` without adding it to `requirements.txt`
- Never run database scripts directly against production without a backup

## Common Problems & Remediation

| Problem | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: No module named 'sqlalchemy'` | Virtualenv not activated | `source .venv/bin/activate` |
| `alembic.util.exc.CommandError: Can't locate revision` | Migrations out of sync | `alembic history` → find divergence → `alembic merge heads` |
| `CORS error in browser` | Backend not running or wrong port | Verify backend is on port 8010; check `VITE_API_URL` in `.env` |
| `Connection refused: 5432` | DB container not running | `docker-compose up -d db` |
| Frontend shows stale data | Vite cache | `rm -rf frontend/node_modules/.vite && npm run dev` |
| `TypeError: Cannot read properties of undefined (reading 'data')` | Flaky test timing | Re-run; known intermittent in MyTeam.test.jsx |

## Dev Ports
| Service | Port |
|---------|------|
| Backend (FastAPI) | 8010 |
| Frontend (Vite) | 5173 |
| PostgreSQL | 5432 |
| pgAdmin (optional) | 5050 |

## Related Skills
- [Database](../database/SKILL.md) — migrations, schema changes
- [Deployment](../deployment/SKILL.md) — Pi production setup
- [Architecture](../architecture/SKILL.md) — how layers connect
