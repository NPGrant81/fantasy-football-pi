# Raspberry Pi Deployment (Nginx + systemd)

This is the recommended production-style setup for Raspberry Pi:
- Raspberry Pi OS Lite (64-bit) provides the base host.
- SSH is enabled during imaging so the Pi can be brought online headlessly.
- Nginx serves frontend static files.
- Nginx reverse proxies backend API routes to FastAPI on `127.0.0.1:8000`.
- systemd keeps the FastAPI backend running.

Quick reference: `docs/PI_UPDATE_CHEATSHEET.md`

## Phase 1: Raspberry Pi OS Setup

Use this section when preparing a fresh Raspberry Pi 5 before any app deploy work.

### Hardware and prerequisites

- Raspberry Pi 5
- microSD card or NVMe boot media
- Official Raspberry Pi 5 USB-C power supply
- Ethernet connection preferred for initial server setup
- Primary workstation with Raspberry Pi Imager installed

### 1. Flash Raspberry Pi OS Lite

On the primary workstation:

1. Open Raspberry Pi Imager.
2. Choose `Raspberry Pi OS (Other)`.
3. Select `Raspberry Pi OS Lite (64-bit)`.
4. Select the target storage device.

Use the advanced settings flow before writing the image:

- Hostname: choose a stable host such as `fantasy-server`
- Username: create a dedicated login user
- Password: set a strong password
- SSH: enable SSH with password authentication for first boot
- Wi-Fi: only preconfigure if Ethernet is not available
- Locale/timezone: set the expected deployment region

The goal is to boot directly into a reachable headless Linux host without needing a monitor or keyboard.

### 2. First boot and network reachability

1. Insert the flashed media into the Pi.
2. Connect Ethernet if available.
3. Power on the device and wait 1-2 minutes for first boot.
4. Determine the host to connect to:
    - Preferred: `<hostname>.local`
    - Fallback: DHCP-assigned IP from the router or DHCP lease table

If `.local` name resolution is unreliable on the workstation, use the Pi IP address directly.

### 3. Verify SSH access

From the workstation:

```bash
ssh <username>@<hostname>.local
```

If hostname resolution fails:

```bash
ssh <username>@<pi_ip_address>
```

Accept the host fingerprint on first connect. Successful login confirms that the image settings, user creation, and network path are all correct.

### 4. Baseline host checks after login

Run these commands immediately after first SSH access:

```bash
whoami
hostnamectl
ip addr show
pwd
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Reconnect after the reboot and confirm the hostname, user, and network interface still look correct.

### 5. Capture deployment inputs before app setup

Confirm these decisions before moving into app deployment and external routing:

- Domain and DNS provider
- Final repo source on the Pi (`git clone` target and branch/ref strategy)
- Backend runtime choice and env file location
- Database location and backup target
- Whether Cloudflare Tunnel will be used for public access

These inputs affect later phases, but they should be known before wiring Nginx, systemd, TLS, or Cloudflare.

## 1. Install Base Packages (Pi)

```bash
sudo apt update
sudo apt install -y nginx python3-venv python3-pip postgresql postgresql-contrib
```

## 2. Backend Setup

```bash
cd /home/pi
# clone or pull repo first
cd fantasy-football-pi/backend
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements-lock.txt
```

Create runtime env file:

```bash
sudo mkdir -p /etc/fantasy-football-pi
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/backend.env.example /etc/fantasy-football-pi/backend.env
sudo nano /etc/fantasy-football-pi/backend.env
```

## 3. Frontend Build

```bash
cd /home/pi/fantasy-football-pi/frontend
npm ci --legacy-peer-deps
npm run build
sudo mkdir -p /var/www/fantasy-football-pi/frontend
sudo rsync -av --delete dist/ /var/www/fantasy-football-pi/frontend/dist/
```

## 4. systemd Backend Service

```bash
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/fantasy-football-backend.service.example /etc/systemd/system/fantasy-football-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now fantasy-football-backend
sudo systemctl status fantasy-football-backend --no-pager
```

## 5. Nginx Site

```bash
sudo cp /home/pi/fantasy-football-pi/deploy/nginx/fantasy-football-pi.conf.example /etc/nginx/sites-available/fantasy-football-pi.conf
sudo nano /etc/nginx/sites-available/fantasy-football-pi.conf
sudo ln -s /etc/nginx/sites-available/fantasy-football-pi.conf /etc/nginx/sites-enabled/fantasy-football-pi.conf
sudo nginx -t
sudo systemctl reload nginx
```

If you are not ready for TLS yet, temporarily use only the HTTP server block.

## 6. Verify

```bash
curl -I http://YOUR_DOMAIN
curl -I http://YOUR_DOMAIN/auth/me
```

Expected:
- Frontend returns `200`/`304`.
- Backend route reaches FastAPI (may return `401` when unauthenticated, which is fine).

## 7. Deploy Update Routine

```bash
cd /home/pi/fantasy-football-pi
git pull

cd backend
./venv/bin/pip install -r requirements-lock.txt

cd ../frontend
npm ci --legacy-peer-deps
npm run build
sudo rsync -av --delete dist/ /var/www/fantasy-football-pi/frontend/dist/

sudo systemctl restart fantasy-football-backend
sudo systemctl reload nginx
```

## 8. How To Decide What Must Be Updated On Pi

Use this flow every time you SSH into the Pi.

### A. Pull and inspect what changed

```bash
cd /home/pi/fantasy-football-pi
git fetch origin
git log --oneline HEAD..origin/main
git diff --name-only HEAD..origin/main
```

Optional helper (recommended):

```bash
cd /home/pi/fantasy-football-pi
bash scripts/pi_update_plan.sh origin/main
```

The helper prints a command checklist based on changed file paths.

### B. Apply updates based on changed paths

Run only the commands required by the files that changed.

| Changed path(s) | Required action on Pi |
| --- | --- |
| `backend/requirements*.txt` | `cd backend && ./venv/bin/pip install -r requirements-lock.txt` |
| `backend/**` (code) | `sudo systemctl restart fantasy-football-backend` |
| `frontend/**` | `cd frontend && npm ci --legacy-peer-deps && npm run build && sudo rsync -av --delete dist/ /var/www/fantasy-football-pi/frontend/dist/` |
| `deploy/nginx/**` | `sudo cp deploy/nginx/fantasy-football-pi.conf.example /etc/nginx/sites-available/fantasy-football-pi.conf && sudo nginx -t && sudo systemctl reload nginx` |
| `deploy/systemd/fantasy-football-backend.service.example` | `sudo cp .../fantasy-football-backend.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart fantasy-football-backend` |
| `deploy/systemd/cloudflared*.example` | copy updated unit files to `/etc/systemd/system/`, then `sudo systemctl daemon-reload` and restart/enable relevant units |
| `deploy/cloudflared/**` | copy updated config to `/etc/cloudflared/config.yml`, then `sudo systemctl restart cloudflared` |
| `ops/backup/**` or `deploy/systemd/microsd-db-backup*.example` | re-copy backup script/units, then `sudo systemctl daemon-reload && sudo systemctl enable --now microsd-db-backup.timer` |
| `docs/**` only | no runtime update required |

### C. Verify after update

```bash
curl -fsS http://127.0.0.1:8000/health
sudo systemctl status fantasy-football-backend --no-pager
sudo systemctl status nginx --no-pager
sudo systemctl status cloudflared --no-pager
sudo systemctl list-timers --all | grep microsd-db-backup
```

If all changed files were docs-only, skip service restarts.

## Notes

- This app currently routes API calls directly by path (`/auth`, `/players`, `/draft`, etc.), not under `/api`.
- The Nginx template in `deploy/nginx/fantasy-football-pi.conf.example` already matches this behavior.
- `python -m backend.manage audit-player-duplicates --fail-on-duplicates` can be run on Pi before deploy cutover as a guard.
- Phase 1 host bring-up intentionally stops before app-specific secrets, TLS, or Cloudflare production cutover.
