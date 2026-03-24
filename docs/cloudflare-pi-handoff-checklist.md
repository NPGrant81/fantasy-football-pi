# Cloudflare Tunnel Pi Handoff Checklist

Date: 2026-03-20
Purpose: Complete Cloudflare tunnel setup from the Raspberry Pi, then return a minimal evidence bundle.

## Scope
This checklist is for the case where `cloudflared` runs on the Pi.

Optional planning helper:

```bash
bash scripts/pi_update_plan.sh origin/main
```

If cloudflared files are in the diff, follow the cloudflared-specific steps below.

## 1. Preflight On Pi
Run:

```bash
cloudflared --version
which cloudflared
sudo ls -la /etc/cloudflared
```

Expected:
- `cloudflared` is installed
- `/etc/cloudflared` exists

## 2. Login And Tunnel Discovery
Run:

```bash
cloudflared tunnel login
cloudflared tunnel list
cloudflared tunnel info ppl-insight-hub-prod1
```

If tunnel does not exist:

```bash
cloudflared tunnel create ppl-insight-hub-prod1
cloudflared tunnel list
```

Capture:
- tunnel UUID for `ppl-insight-hub-prod1`

## 3. Configure Tunnel On Pi
From repository root on Pi:

```bash
sudo mkdir -p /etc/cloudflared
sudo cp deploy/cloudflared/config.ppl-insight-hub-prod1.example.yml /etc/cloudflared/config.yml
sudo nano /etc/cloudflared/config.yml
```

Set:
- `credentials-file: /etc/cloudflared/<tunnel-uuid>.json`
- Keep service target as `http://127.0.0.1:80` if nginx is on the Pi

Validate config:

```bash
sudo cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate
```

## 4. DNS Route Creation
Run:

```bash
cloudflared tunnel route dns ppl-insight-hub-prod1 pplinsighthub.com
cloudflared tunnel route dns ppl-insight-hub-prod1 www.pplinsighthub.com
```

Confirm in Cloudflare dashboard:
- Zero Trust -> Networks -> Tunnels -> `ppl-insight-hub-prod1` has both public hostnames
- DNS records are proxied

## 5. Install systemd Units
From repository root on Pi:

```bash
sudo bash deploy/systemd/install_cloudflared_monitoring.sh
```

This installer now:
- checks root and `cloudflared` availability
- checks `/etc/cloudflared/config.yml`
- creates `cloudflared` system user/group if missing
- installs cloudflared service + watchdog timer

## 6. Service Validation
Run:

```bash
sudo systemctl status cloudflared --no-pager
sudo systemctl status cloudflared-watchdog.timer --no-pager
sudo journalctl -u cloudflared -n 200 --no-pager
```

Expected:
- `cloudflared` active
- watchdog timer active
- no recurring auth/config failures in logs

## 7. Public Endpoint Validation
Run:

```bash
curl -I https://pplinsighthub.com
curl -I https://pplinsighthub.com/health
curl -I https://pplinsighthub.com/auth/me
```

Expected:
- homepage: `200` or `304`
- `/health`: `200`
- `/auth/me`: `401` is acceptable when unauthenticated

## 8. Evidence Bundle To Return
Paste these outputs back:
- `cloudflared tunnel list`
- `cloudflared tunnel info ppl-insight-hub-prod1`
- `sudo systemctl status cloudflared --no-pager`
- `sudo systemctl status cloudflared-watchdog.timer --no-pager`
- `curl -I https://pplinsighthub.com/health`

## Common Fixes
- `ExecStart` failure:
  - service file uses `cloudflared` via PATH, verify `which cloudflared`
- credential mismatch:
  - verify `credentials-file` UUID matches tunnel UUID
- route works for site but not API:
  - verify nginx forwards `/health` and API route families to `127.0.0.1:8000`
