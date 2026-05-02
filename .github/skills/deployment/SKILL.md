---
name: deployment
description: 'Raspberry Pi production deployment, Nginx reverse proxy, Cloudflare Tunnel setup, systemd service management, Docker, and release process for Fantasy Football PI. Use when: deploying to the Pi, configuring Nginx, setting up or renewing Cloudflare tunnels, managing systemd services, or performing production releases.'
argument-hint: 'Optional: focus area (pi-setup | nginx | cloudflare | systemd | docker | release | rollback)'
---

# Deployment

## Why This Exists
Fantasy Football PI runs in production on a Raspberry Pi 4 with a Cloudflare Tunnel providing HTTPS access without exposing the Pi's IP. The deployment stack is intentionally simple: systemd manages services, Nginx handles proxying, and Cloudflare handles TLS and DNS.

## Production Stack
```
Internet
  └── Cloudflare Tunnel (TLS termination, DNS)
        └── cloudflared (systemd service on Pi)
              └── Nginx (reverse proxy on Pi :80)
                    ├── /api/*    → FastAPI backend :8010
                    └── /*        → React static files (built)
```

## Deployment Directory Structure
```
deploy/
  nginx/          ← Nginx site config
  systemd/        ← Service unit files for backend, cloudflared
  cloudflared/    ← Tunnel configuration
```

## Services Managed by systemd

| Service | Unit File | Purpose |
|---------|-----------|---------|
| `fantasy-backend` | `deploy/systemd/fantasy-backend.service` | FastAPI (uvicorn) |
| `cloudflared` | `deploy/systemd/cloudflared.service` | Cloudflare tunnel |

### Common systemd commands
```bash
# Check status
sudo systemctl status fantasy-backend
sudo systemctl status cloudflared

# Restart after code update
sudo systemctl restart fantasy-backend

# View live logs
sudo journalctl -u fantasy-backend -f
sudo journalctl -u cloudflared -f

# Enable on boot
sudo systemctl enable fantasy-backend
```

## Release Process (Pi deployment)

### 1. Pre-release checks
```bash
# On dev machine — ensure all tests pass
cd frontend && npm test -- --run && npm run build
cd ../backend && python -m pytest
```

### 2. SSH to Pi
```bash
ssh pi@<pi-hostname>
cd /home/pi/fantasy-football-pi
```

### 3. Pull latest from main
```bash
git pull origin main
```

### 4. Backend update
```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && alembic upgrade head
```

### 5. Frontend build
```bash
cd frontend
npm install
npm run build
# Built files in frontend/dist/ — Nginx serves these as static
```

### 6. Restart services
```bash
sudo systemctl restart fantasy-backend
sudo systemctl status fantasy-backend   # verify running
```

### 7. Smoke test
```bash
curl -s http://localhost:8010/health | jq .
# Expected: {"status": "ok"}
```

### 8. Post-deploy issue close-out notes (required)
After production verification, add close-out notes back to every related GitHub issue (for example: #46, #48, #50) so tracking reflects real deployment status, not just merge status.

Minimum note content:
- Deployment status (`deployed` / `partially deployed` / `rolled back`)
- Validation evidence (health check, key endpoint/UI checks)
- Commit/PR reference
- Follow-up items (if any)

Suggested issue comment template:
```markdown
## Close-Out Notes
- Status: Deployed to production on YYYY-MM-DD
- Scope: [short summary]
- Validation:
  - [x] `/health` returned `{"status":"ok"}`
  - [x] Backend endpoint verified: `GET /analytics/...`
  - [x] Frontend view verified in Analytics Dashboard
- Evidence: PR #<N>, commit <sha>
- Follow-ups: None / Refs #<N>
```

If work is merged but not yet deployed, post a note that clearly says `merged, pending deployment`.

### 9. Copilot feedback follow-through (required)
Deployment notes must reflect any post-PR Copilot fixes that changed behavior.

Track this in both places:
- PR notes (`docs/PR_NOTES.md`): summarize Copilot threads and follow-up commits
- Related issues: include a one-line note if deployment includes Copilot-driven fixes after initial merge

Suggested issue addendum:
```markdown
- Copilot feedback follow-up: included in deployment (commit <sha>, PR #<N>)
```

## Nginx Configuration
Key config at `deploy/nginx/fantasy-football.conf`:
- `/api/` → proxied to `http://127.0.0.1:8010`
- `/` → static files at `/home/pi/fantasy-football-pi/frontend/dist`
- Cloudflare terminates TLS; Pi only needs HTTP on :80

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8010/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location / {
    root /home/pi/fantasy-football-pi/frontend/dist;
    try_files $uri $uri/ /index.html;
}
```

## Cloudflare Tunnel

### Check tunnel status
```bash
sudo systemctl status cloudflared
cloudflared tunnel info fantasy-pi
```

### Renew tunnel token (if expired/rotated)
```bash
# Get new token from Cloudflare dashboard
# Update in systemd unit or .env:
sudo nano /etc/systemd/system/cloudflared.service
# Update ExecStart with new token
sudo systemctl daemon-reload
sudo systemctl restart cloudflared
```

### Full tunnel setup from scratch
See `docs/CLOUDFLARE_TUNNEL_SETUP.md` for the complete walkthrough.

## Docker (Dev/Test Only)
Docker is used for the **development database only**. Production runs PostgreSQL natively on the Pi.

```bash
# Start dev database
docker-compose up -d db

# Stop
docker-compose down

# View logs
docker-compose logs db
```

## Always Do
- Run `alembic upgrade head` after every deployment that includes model changes
- Restart `fantasy-backend` after any backend code change
- Rebuild frontend (`npm run build`) after any frontend code change
- Check `journalctl -u fantasy-backend -f` for errors after restart
- Back up the database before migrations: `pg_dump fantasy_football > backup_$(date +%Y%m%d).sql`
- Test the `/health` endpoint immediately after restart
- Post close-out notes on each related GitHub issue after deployment verification
- Ensure close-out notes mention any Copilot-driven follow-up fixes shipped in that deploy

## Never Do
- Never deploy uncommitted changes — always deploy from a tagged commit or `main`
- Never run `alembic downgrade` in production without a full backup
- Never expose the Pi's IP directly — always route through Cloudflare Tunnel
- Never run `npm install` on the Pi in production — build on dev and copy `dist/`, or build on Pi but not on Pi hardware constrained by memory for heavy npm installs
- Never store the Cloudflare tunnel token in the git repo
- Never mark an issue complete without posting validation notes (or explicit pending-deploy note)

## Rollback Procedure
```bash
# 1. Find last known good commit
git log --oneline -10

# 2. Checkout that commit (or revert)
git checkout <commit-hash>

# 3. Rebuild frontend if needed
cd frontend && npm run build

# 4. Downgrade database if migration was applied
cd backend && alembic downgrade -1   # (only if migration is reversible)

# 5. Restart service
sudo systemctl restart fantasy-backend
```

## Common Problems & Remediation

| Problem | Fix |
|---------|-----|
| 502 Bad Gateway | Backend not running — `sudo systemctl restart fantasy-backend` |
| Tunnel not connecting | `sudo systemctl restart cloudflared` + check token |
| Static files not updating | Ran `npm run build` but Nginx cache — `sudo systemctl reload nginx` |
| Port 8010 already in use | `pkill -f uvicorn` then restart service |
| Migration fails on Pi | Check `alembic history`; may need `alembic merge heads` |

## Related Skills
- [Project Bootstrap](../project-bootstrap/SKILL.md) — local dev setup
- [Git Workflow](../git-workflow/SKILL.md) — release branching
- [Maintenance](../maintenance/SKILL.md) — regular Pi maintenance tasks
- [Security](../security/SKILL.md) — Cloudflare, secrets management
