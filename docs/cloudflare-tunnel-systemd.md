# Cloudflare Tunnel systemd Runbook (Raspberry Pi)

Date: 2026-03-10
Related Issue: #208

## Goal
Provide a reproducible systemd setup so `cloudflared` starts on boot, restarts on failures, and is observable with `journalctl`.

## Source of truth files in repo
- Service template: `deploy/systemd/cloudflared.service.example`
- Watchdog service template: `deploy/systemd/cloudflared-watchdog.service.example`
- Watchdog timer template: `deploy/systemd/cloudflared-watchdog.timer.example`
- One-command installer: `deploy/systemd/install_cloudflared_monitoring.sh`
- Tunnel config template: `deploy/cloudflared/config.ppl-insight-hub-prod1.example.yml`

## Directory structure on Pi
- Tunnel config: `/etc/cloudflared/config.yml`
- Tunnel credentials JSON: `/etc/cloudflared/<tunnel-id>.json`
- Unit files: `/etc/systemd/system/cloudflared*.service`, `/etc/systemd/system/cloudflared-watchdog.timer`

## 1. Prerequisites
```bash
cloudflared --version
id cloudflared || echo "cloudflared user missing"
sudo ls -la /etc/cloudflared
sudo test -f /etc/cloudflared/config.yml && echo "config present"
```

Expected:
- `cloudflared` binary installed
- `cloudflared` system user exists (or will be created by the installer)
- `config.yml` present
- tunnel credentials JSON present

## 2. Install/Update systemd units
Option A: one command (recommended)
```bash
cd /opt/fantasy-football-pi
sudo bash deploy/systemd/install_cloudflared_monitoring.sh
id cloudflared
```

Option B: manual copy
```bash
cd /opt/fantasy-football-pi
sudo cp deploy/systemd/cloudflared.service.example /etc/systemd/system/cloudflared.service
sudo cp deploy/systemd/cloudflared-watchdog.service.example /etc/systemd/system/cloudflared-watchdog.service
sudo cp deploy/systemd/cloudflared-watchdog.timer.example /etc/systemd/system/cloudflared-watchdog.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared.service
sudo systemctl enable --now cloudflared-watchdog.timer
```

## 3. Validate service health
```bash
sudo systemctl status cloudflared --no-pager
sudo systemctl status cloudflared-watchdog.timer --no-pager
sudo journalctl -u cloudflared -n 200 --no-pager
cloudflared tunnel info ppl-insight-hub-prod1
```

## 4. Reboot validation
```bash
sudo reboot
```
After reboot:
```bash
sudo systemctl is-enabled cloudflared
sudo systemctl is-active cloudflared
sudo systemctl is-enabled cloudflared-watchdog.timer
sudo systemctl is-active cloudflared-watchdog.timer
```

Expected:
- both units are `enabled`
- both units are `active`

## 5. Failure and reconnect behavior checks
Simulate service failure:
```bash
sudo systemctl stop cloudflared
sleep 3
sudo systemctl status cloudflared --no-pager
```

Simulate network disruption and observe reconnect:
```bash
sudo journalctl -u cloudflared --since "-10m" --no-pager
```

Public endpoint check:
```bash
curl -i https://pplinsighthub.com/health
```

## Troubleshooting
### Service fails to start
Checks:
```bash
sudo systemctl status cloudflared --no-pager
sudo journalctl -u cloudflared -n 200 --no-pager
```
Common fixes:
- wrong `ExecStart` binary path in unit
- invalid `/etc/cloudflared/config.yml`
- missing/incorrect tunnel credentials JSON
- missing `credentials-file:` entry in `/etc/cloudflared/config.yml`
- missing `cloudflared` service user/group

Binary path note:
- Some Pi installs place `cloudflared` in `/usr/local/bin`, others in `/usr/bin`.
- The service template uses `Environment=PATH=/usr/local/bin:/usr/bin:/bin` plus `/usr/bin/env cloudflared` so either location works.

### Tunnel starts but traffic does not route
Checks:
```bash
cloudflared tunnel list
cloudflared tunnel info ppl-insight-hub-prod1
sudo cat /etc/cloudflared/config.yml
```
Common fixes:
- `tunnel:` ID mismatch between config and credentials
- incorrect ingress `service` target
- DNS route not pointing to tunnel UUID endpoint

### Watchdog not triggering restart
Checks:
```bash
sudo systemctl status cloudflared-watchdog.timer --no-pager
sudo systemctl list-timers --all | grep cloudflared-watchdog
```
Common fixes:
- timer not enabled
- watchdog service file not copied to `/etc/systemd/system`
- `daemon-reload` not run after unit updates

## Acceptance mapping (#208)
- Boot persistence: yes (`enable --now cloudflared.service`)
- Auto-restart on failure: yes (`Restart=on-failure`)
- Logs available: yes (`journalctl -u cloudflared`)
- No manual upkeep required: yes (service + watchdog timer)
- Reproducible documentation: yes (this runbook)
