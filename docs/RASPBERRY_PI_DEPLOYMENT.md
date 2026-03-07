# Raspberry Pi Deployment (Nginx + systemd)

This is the recommended production-style setup for Raspberry Pi:
- Nginx serves frontend static files.
- Nginx reverse proxies backend API routes to FastAPI on `127.0.0.1:8000`.
- systemd keeps the FastAPI backend running.

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

## Notes

- This app currently routes API calls directly by path (`/auth`, `/players`, `/draft`, etc.), not under `/api`.
- The Nginx template in `deploy/nginx/fantasy-football-pi.conf.example` already matches this behavior.
- `python -m backend.manage audit-player-duplicates --fail-on-duplicates` can be run on Pi before deploy cutover as a guard.
