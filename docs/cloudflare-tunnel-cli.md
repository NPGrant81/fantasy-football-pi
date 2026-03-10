# Cloudflare Tunnel CLI Runbook

Date: 2026-03-10
Related Issue: #207

## Goal
Install and operate Cloudflare Tunnel via official `cloudflared` CLI for persistent Raspberry Pi routing and optional ephemeral dev tunnels.

## Scope
- CLI install and login
- named tunnel creation
- `config.yml` routing for frontend + backend
- DNS route setup
- Pi persistence with systemd
- troubleshooting + validation

## 1. Install cloudflared
### Raspberry Pi (Debian/Ubuntu)
```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install -y cloudflared
cloudflared --version
```

### Windows (dev workstation)
- Use official Cloudflare package/installer and verify:
```powershell
cloudflared.exe --version
```

## 2. Authenticate and create named tunnel
```bash
cloudflared tunnel login
cloudflared tunnel create fantasy-football-prod
```

This creates credentials JSON under `~/.cloudflared/` (or OS-equivalent).
Move credentials to `/etc/cloudflared/` on Pi for systemd operation.

## 3. Configure tunnel routing (frontend + backend)
Use template:
- `deploy/cloudflared/config.cli.example.yml`

Copy on Pi:
```bash
sudo mkdir -p /etc/cloudflared
sudo cp deploy/cloudflared/config.cli.example.yml /etc/cloudflared/config.yml
sudo nano /etc/cloudflared/config.yml
```

Set values:
- `tunnel: <tunnel-name-or-uuid>`
- `credentials-file: /etc/cloudflared/<tunnel-uuid>.json`
- hostnames (example):
  - `app.pplinsighthub.com` -> frontend (`127.0.0.1:80`)
  - `api.pplinsighthub.com` -> backend (`127.0.0.1:8000`)

## 4. DNS routing
```bash
cloudflared tunnel route dns fantasy-football-prod app.pplinsighthub.com
cloudflared tunnel route dns fantasy-football-prod api.pplinsighthub.com
```

Validate:
```bash
dig +short app.pplinsighthub.com
dig +short api.pplinsighthub.com
```

## 5. Persistent service on Raspberry Pi
Use:
- `deploy/systemd/cloudflared.service.example`
- `deploy/systemd/cloudflared-watchdog.service.example`
- `deploy/systemd/cloudflared-watchdog.timer.example`

One-command install:
```bash
sudo bash deploy/systemd/install_cloudflared_monitoring.sh
```

Manual alternative:
```bash
sudo cp deploy/systemd/cloudflared.service.example /etc/systemd/system/cloudflared.service
sudo cp deploy/systemd/cloudflared-watchdog.service.example /etc/systemd/system/cloudflared-watchdog.service
sudo cp deploy/systemd/cloudflared-watchdog.timer.example /etc/systemd/system/cloudflared-watchdog.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared.service
sudo systemctl enable --now cloudflared-watchdog.timer
```

## 6. Local ephemeral tunnel option
For day-to-day dev sharing, ephemeral tunnel still works:
```bash
cloudflared tunnel --url http://127.0.0.1:5173
cloudflared tunnel --url http://127.0.0.1:8010
```

## 7. Verification checklist
```bash
# service health
sudo systemctl status cloudflared --no-pager
sudo journalctl -u cloudflared -n 200 --no-pager

# app + api reachability
curl -I https://app.pplinsighthub.com
curl -I https://api.pplinsighthub.com/health

# auth path should respond (401 or 200 depending session)
curl -I https://api.pplinsighthub.com/auth/me
```

## Troubleshooting
### Login opens browser but tunnel not created
- confirm Cloudflare account and zone permissions
- rerun `cloudflared tunnel login`

### Tunnel starts then exits
- check `credentials-file` path and permissions
- verify tunnel UUID/name in config matches credentials

### DNS resolves but backend unreachable
- verify backend bound to `127.0.0.1:8000`
- verify ingress route in `config.yml` points to the correct backend port

### Reboot loses tunnel
- ensure unit is enabled:
```bash
sudo systemctl is-enabled cloudflared
sudo systemctl is-active cloudflared
```

## Acceptance mapping (#207)
- CLI install documented: yes
- named tunnel creation documented: yes
- config template for app+api routing: yes
- DNS route workflow documented: yes
- Pi persistence via systemd documented: yes
- ephemeral dev tunnel option documented: yes
