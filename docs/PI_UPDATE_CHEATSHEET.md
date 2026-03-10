# Raspberry Pi Update Cheatsheet

Use this when deploying latest repo changes on Pi.

## Primary instruction files
- Main runbook: `docs/RASPBERRY_PI_DEPLOYMENT.md`
- Auto planner script: `scripts/pi_update_plan.sh`
- Backup restore guide: `docs/restore.md`

## Fast path (recommended)
```bash
cd /home/pi/fantasy-football-pi
git fetch origin
bash scripts/pi_update_plan.sh origin/main
```

Then run the printed commands in order.

## Minimal manual flow
```bash
cd /home/pi/fantasy-football-pi
git pull --ff-only
```

If backend changed:
```bash
cd backend
./venv/bin/pip install -r requirements-lock.txt
cd ..
sudo systemctl restart fantasy-football-backend
```

If frontend changed:
```bash
cd frontend
npm ci --legacy-peer-deps
npm run build
sudo rsync -av --delete dist/ /var/www/fantasy-football-pi/frontend/dist/
cd ..
```

If nginx config changed:
```bash
sudo cp deploy/nginx/fantasy-football-pi.conf.example /etc/nginx/sites-available/fantasy-football-pi.conf
sudo nginx -t
sudo systemctl reload nginx
```

If cloudflared config/units changed:
```bash
sudo cp deploy/cloudflared/config.ppl-insight-hub-prod1.example.yml /etc/cloudflared/config.yml
sudo cp deploy/systemd/cloudflared*.example /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart cloudflared
```

If backup automation changed:
```bash
sudo install -m 0755 ops/backup/microsd_db_backup.sh /opt/fantasy-football-pi/ops/backup/microsd_db_backup.sh
sudo cp deploy/systemd/microsd-db-backup.service.example /etc/systemd/system/microsd-db-backup.service
sudo cp deploy/systemd/microsd-db-backup.timer.example /etc/systemd/system/microsd-db-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now microsd-db-backup.timer
```

## Final verification
```bash
curl -fsS http://127.0.0.1:8000/health
sudo systemctl status fantasy-football-backend --no-pager
sudo systemctl status nginx --no-pager
sudo systemctl status cloudflared --no-pager
sudo systemctl list-timers --all | grep microsd-db-backup
```
