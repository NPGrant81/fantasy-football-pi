# Raspberry Pi Action Checklist (Phone-Friendly)

Use this when you're working from an iPhone or another mobile device and need a short, direct list of actions to run on the Pi.

## 1) Open a terminal on the Pi

```bash
ssh pi@<pi-hostname-or-ip>
```

If you are already on the Pi shell, skip this step.

## 2) Update the repo

```bash
cd /home/pi/fantasy-football-pi
git fetch origin
git pull --ff-only
```

## 3) Check what changed

```bash
bash scripts/pi_update_plan.sh origin/main
```

Then follow the recommended commands printed by the script.

## 4) If backend or app code changed

```bash
cd /home/pi/fantasy-football-pi
sudo systemctl restart fantasy-football-backend
```

If dependencies changed, also run:

```bash
cd /home/pi/fantasy-football-pi/backend
./venv/bin/pip install -r requirements-lock.txt
```

## 5) If frontend changed

```bash
cd /home/pi/fantasy-football-pi/frontend
npm ci --legacy-peer-deps
npm run build
sudo rsync -av --delete dist/ /var/www/fantasy-football-pi/frontend/dist/
```

## 6) If nginx changed

```bash
sudo cp /home/pi/fantasy-football-pi/deploy/nginx/fantasy-football-pi.conf.example /etc/nginx/sites-available/fantasy-football-pi.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 7) If backup automation changed

```bash
sudo install -m 0755 /home/pi/fantasy-football-pi/ops/backup/microsd_db_backup.sh /opt/fantasy-football-pi/ops/backup/microsd_db_backup.sh
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/microsd-db-backup.service.example /etc/systemd/system/microsd-db-backup.service
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/microsd-db-backup.timer.example /etc/systemd/system/microsd-db-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now microsd-db-backup.timer
```

## 8) Run the recovery validation check

```bash
cd /home/pi/fantasy-football-pi
DB_URL="sqlite:////var/lib/fantasy-football-pi/app.db" \
BACKUP_DIR="/var/backups/fantasy-football-pi" \
./scripts/validate_backup_recovery.sh
```

If the app is using Postgres instead, replace the `DB_URL` value with the production Postgres DSN.

## 9) Confirm service health

```bash
curl -fsS http://127.0.0.1:8000/health
sudo systemctl status fantasy-football-backend --no-pager
sudo systemctl status nginx --no-pager
sudo systemctl list-timers --all | grep microsd-db-backup
```

## 10) If something is broken

```bash
sudo journalctl -u fantasy-football-backend -n 100 --no-pager
sudo journalctl -u nginx -n 100 --no-pager
sudo systemctl list-timers --all | grep microsd-db-backup
```

## Quick summary

For most routine Pi updates:

```bash
cd /home/pi/fantasy-football-pi
git pull --ff-only
bash scripts/pi_update_plan.sh origin/main
sudo systemctl restart fantasy-football-backend
curl -fsS http://127.0.0.1:8000/health
```

If backup safety is the issue, run the validation script first and only then do the service or restore actions.
