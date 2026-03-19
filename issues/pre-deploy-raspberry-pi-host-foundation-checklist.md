# Title
Pre-Deploy Raspberry Pi Host Foundation Checklist (Packages, Hardening, Service Readiness)

## Parent
- Parent issue: #79
- Type: Child execution issue
- Labels: `devops`, `security`, `deployment`

## Summary
Track baseline Raspberry Pi host preparation while app deployment work is still in progress. This issue covers package foundation and host-level hardening that is safe to do before final app cutover.

## Scope
- Install baseline OS packages used by deploy/runbooks.
- Apply firewall baseline and intrusion-prevention defaults.
- Verify core host services and command availability.
- Capture completion notes and verification output.

## Out of Scope (defer until app-ready)
- Final app Nginx site + TLS cert wiring.
- Production Cloudflare tunnel credential placement and service cutover.
- Final backend secrets and production env file values.
- Database backup timer activation bound to final database path.

## Checklist
- [x] Install baseline packages: git, curl, build-essential, nodejs, npm, python3, python3-pip, python3-venv, nginx, ufw, fail2ban, htop, tmux, logrotate, net-tools
- [x] Correct package naming (`fail2ban`, not `fall2ban`)
- [x] Enable UFW and allow `OpenSSH`
- [x] Allow `Nginx Full` profile in UFW
- [x] Enable and start `nginx`
- [x] Enable and start `fail2ban`
- [x] Verify fail2ban jail status (`sshd` active)
- [x] Verify binary/toolchain availability
- [x] Add parent issue completion note with command outputs and next-step defer list

## Execution Notes (2026-03-18)
### Package delta discovered
Missing before run: `ufw`, `fail2ban`, `tmux`

### Commands executed
```bash
sudo apt update && sudo apt install -y ufw fail2ban tmux
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo systemctl enable --now fail2ban
sudo systemctl enable --now nginx
sudo ufw status verbose
sudo fail2ban-client status
```

### Verification snapshot
- `ufw` status: active
- UFW defaults: deny incoming, allow outgoing
- Allowed inbound: OpenSSH (22), Nginx Full (80/443)
- `fail2ban` status: active with jail list `sshd`
- `nginx` status: enabled + active

### Version snapshot
- Node: `v20.19.2`
- npm: `9.2.0`
- Python: `3.13.5`
- pip: `25.1.1`
- nginx: `1.26.3`
- tmux: `3.5a`

## Status
- Execution status: baseline host foundation complete
- GitHub issue status target: remain open until app-coupled follow-on items are completed
- Parent update note draft: `issues/pre-deploy-raspberry-pi-host-foundation-parent-note.md`

## Pre-Cloudflare Handoff
Complete these host-side items before production tunnel cutover:

- Confirm final app Nginx site file and backend upstream wiring on the Pi.
- Finalize backend production env values and secrets placement.
- Confirm final database target and enable the backup timer against that path.
- Verify local origin readiness over HTTP on the Pi before attaching Cloudflare.

Cloudflare-specific credential placement and service cutover stay in the Cloudflare issue/runbooks.

## Pre-Cloudflare Execution Checklist

### 1. Finalize backend runtime env

- Source template: `deploy/systemd/backend.env.example`
- Target path on Pi: `/etc/fantasy-football-pi/backend.env`

Commands:

```bash
sudo mkdir -p /etc/fantasy-football-pi
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/backend.env.example /etc/fantasy-football-pi/backend.env
sudo nano /etc/fantasy-football-pi/backend.env
sudo grep -E '^(DATABASE_URL|FRONTEND_ALLOWED_ORIGINS|ALLOWED_HOSTS)=' /etc/fantasy-football-pi/backend.env
```

Required review points:

- `DATABASE_URL` points to the real production database target.
- `FRONTEND_ALLOWED_ORIGINS` uses the intended public origin.
- `ALLOWED_HOSTS` includes the public domain plus local loopback values.
- `ALLOW_ALL_ORIGINS=0` remains in place for production.

### 2. Install and verify backend systemd service

- Source template: `deploy/systemd/fantasy-football-backend.service.example`
- Target path on Pi: `/etc/systemd/system/fantasy-football-backend.service`

Commands:

```bash
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/fantasy-football-backend.service.example /etc/systemd/system/fantasy-football-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now fantasy-football-backend
sudo systemctl status fantasy-football-backend --no-pager
curl -fsS http://127.0.0.1:8000/health
```

Verification target:

- Service is `enabled` and `active`.
- Health endpoint responds on `127.0.0.1:8000`.

### 3. Wire the final Nginx site to the local origin

- Source template: `deploy/nginx/fantasy-football-pi.conf.example`
- Target path on Pi: `/etc/nginx/sites-available/fantasy-football-pi.conf`

Commands:

```bash
sudo cp /home/pi/fantasy-football-pi/deploy/nginx/fantasy-football-pi.conf.example /etc/nginx/sites-available/fantasy-football-pi.conf
sudo nano /etc/nginx/sites-available/fantasy-football-pi.conf
sudo ln -sf /etc/nginx/sites-available/fantasy-football-pi.conf /etc/nginx/sites-enabled/fantasy-football-pi.conf
sudo nginx -t
sudo systemctl reload nginx
curl -I http://127.0.0.1/
curl -I http://127.0.0.1/auth/me
```

Required adjustments before reload:

- Replace `YOUR_DOMAIN` with the real domain.
- If Cloudflare cutover has not happened yet, use only the HTTP server block or otherwise avoid forcing an HTTPS redirect that the host cannot yet satisfy.
- Confirm the API proxy block still targets `http://127.0.0.1:8000`.

Verification target:

- `nginx -t` passes.
- Frontend origin responds on local HTTP.
- `/auth/me` reaches FastAPI and may return `401`, which is acceptable before login.

### 4. Install and enable backup automation against the final DB target

- Script source: `ops/backup/microsd_db_backup.sh`
- Unit templates: `deploy/systemd/microsd-db-backup.service.example`, `deploy/systemd/microsd-db-backup.timer.example`

Commands:

```bash
sudo mkdir -p /opt/fantasy-football-pi/ops/backup
sudo install -m 0755 /home/pi/fantasy-football-pi/ops/backup/microsd_db_backup.sh /opt/fantasy-football-pi/ops/backup/microsd_db_backup.sh
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/microsd-db-backup.service.example /etc/systemd/system/microsd-db-backup.service
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/microsd-db-backup.timer.example /etc/systemd/system/microsd-db-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now microsd-db-backup.timer
sudo systemctl start microsd-db-backup.service
sudo systemctl status microsd-db-backup.service --no-pager
sudo systemctl list-timers --all | grep microsd-db-backup
```

Required review points:

- The backup mount exists and is writable.
- The DB URL used by the backup script matches the final runtime database.
- A test backup artifact is created successfully before relying on the timer.

### 5. Final local-origin smoke check before Cloudflare

Run this sequence on the Pi after env, backend, Nginx, and backup steps are complete:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -I http://127.0.0.1/
curl -I http://127.0.0.1/auth/me
sudo systemctl status fantasy-football-backend --no-pager
sudo systemctl status nginx --no-pager
sudo systemctl status fail2ban --no-pager
sudo systemctl list-timers --all | grep microsd-db-backup
```

Exit criteria before moving to Cloudflare:

- Backend health endpoint returns successfully.
- Nginx serves the frontend locally.
- Nginx proxies backend routes locally.
- Backup timer is loaded and a manual backup run succeeded.
- No remaining edits are needed in backend env or Nginx origin wiring.

## Acceptance Criteria
- Host has baseline packages required for app deployment runbooks.
- Firewall baseline is active without locking out SSH.
- Intrusion-prevention service is active and monitoring SSH.
- Notes include exact commands and verification outputs.
- Deferred app-coupled tasks are explicitly documented.

## Follow-on
After app readiness is confirmed, execute deferred tasks in deployment runbooks and update parent #79 with final cutover status.
