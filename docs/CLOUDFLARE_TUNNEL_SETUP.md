# Cloudflare Tunnel Setup (pplinsighthub.com)

This guide covers production tunnel cutover after the local Raspberry Pi origin is already verified.

Deployment target:
- Domain: `pplinsighthub.com`
- Tunnel name: `ppl-insight-hub-prod1`
- Origin on Pi: `http://127.0.0.1:80`

For lower-level references, see:
- `docs/cloudflare-tunnel-cli.md`
- `docs/cloudflare-tunnel-systemd.md`

## Cloudflare readiness checklist

These are the minimum items that must be in place when the app is ready for real deployment.

- `cloudflared` is installed on the Raspberry Pi and resolves at `/usr/bin/cloudflared`
- `command -v cloudflared` resolves successfully on the Raspberry Pi
- `/etc/cloudflared/config.yml` exists and includes both `tunnel:` and `credentials-file:`
- The named-tunnel credentials JSON exists at `/etc/cloudflared/<tunnel-uuid>.json`
- The `cloudflared` system user/group exists on the Pi
- Nginx is serving the intended local origin on `127.0.0.1:80`
- Backend env production values are finalized, especially `ALLOWED_HOSTS` and `FRONTEND_ALLOWED_ORIGINS`
- The Cloudflare tunnel routes for `pplinsighthub.com` and `www.pplinsighthub.com` point to the named tunnel
- `cloudflared.service` and `cloudflared-watchdog.timer` are enabled and healthy
- Reboot validation has passed on the Pi

If any item above is missing, treat the setup as not deployment-ready yet.

## Setup-only test mode

If the application is not ready to deploy yet, you can still validate the infrastructure path.

What you can test safely:
- `cloudflared` install and systemd startup on the Pi
- Tunnel config and credentials loading
- DNS routing for `pplinsighthub.com`
- Public reachability to an Nginx-served placeholder or static page

What you should not treat as complete yet:
- backend/API reachability
- authenticated routes
- production `/health` semantics through FastAPI
- final backup validation tied to the real database target

Recommended temporary setup for infrastructure-only testing:
- Make sure Nginx serves any simple HTTP response on `127.0.0.1:80`
- Use a temporary tunnel healthcheck path of `/` instead of `/health` if the backend is not deployed yet
- Verify public `200`/`304` on the root page only

Once the app is actually deployed, switch back to the full production checks in this guide.

## 1. Preconditions before cutover

Do not start tunnel cutover until the pre-Cloudflare host-side checklist is complete.

Required local-origin checks on the Pi:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -I http://127.0.0.1/
curl -I http://127.0.0.1/auth/me
sudo systemctl status fantasy-football-backend --no-pager
sudo systemctl status nginx --no-pager
```

Expected:
- FastAPI health responds locally.
- Nginx serves the frontend locally.
- `/auth/me` reaches the backend and may return `401` when unauthenticated.

If you are running setup-only test mode, replace these preconditions with:

```bash
curl -I http://127.0.0.1/
sudo systemctl status nginx --no-pager
```

Expected in setup-only mode:
- Nginx responds locally on port `80`
- You have a stable local origin for Cloudflare to reach

## 2. Install cloudflared on the Raspberry Pi

```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install -y cloudflared
cloudflared --version
command -v cloudflared
```

Verification target:
- `cloudflared` is installed and `command -v cloudflared` resolves successfully.

## 3. Stage tunnel credentials and config on the Pi

Source template:
- `deploy/cloudflared/config.ppl-insight-hub-prod1.example.yml`

Target paths on Pi:
- `/etc/cloudflared/config.yml`
- `/etc/cloudflared/<tunnel-credentials>.json`

Commands:

```bash
sudo mkdir -p /etc/cloudflared
sudo cp /home/pi/fantasy-football-pi/deploy/cloudflared/config.ppl-insight-hub-prod1.example.yml /etc/cloudflared/config.yml
sudo nano /etc/cloudflared/config.yml
sudo ls -la /etc/cloudflared
```

Required review points:
- The `tunnel:` value matches the real tunnel name or UUID.
- The `credentials-file:` path points to the real credentials JSON stored in `/etc/cloudflared/`.
- The credentials JSON for that tunnel exists in `/etc/cloudflared/`.
- The ingress service target remains `http://127.0.0.1:80` when cloudflared runs on the Pi.
- `pplinsighthub.com` and `www.pplinsighthub.com` both point to the same local origin unless you intentionally split them.
- If the app is not deployed yet, temporarily change the healthcheck path from `/health` to `/`.

## 4. Install the cloudflared systemd service on the Pi

Source files:
- `deploy/systemd/cloudflared.service.example`
- `deploy/systemd/cloudflared-watchdog.service.example`
- `deploy/systemd/cloudflared-watchdog.timer.example`
- `deploy/systemd/install_cloudflared_monitoring.sh`

Recommended install:

```bash
cd /home/pi/fantasy-football-pi
sudo bash deploy/systemd/install_cloudflared_monitoring.sh
id cloudflared
sudo systemctl status cloudflared --no-pager
sudo systemctl status cloudflared-watchdog.timer --no-pager
sudo journalctl -u cloudflared -n 100 --no-pager
```

Manual alternative:

```bash
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/cloudflared.service.example /etc/systemd/system/cloudflared.service
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/cloudflared-watchdog.service.example /etc/systemd/system/cloudflared-watchdog.service
sudo cp /home/pi/fantasy-football-pi/deploy/systemd/cloudflared-watchdog.timer.example /etc/systemd/system/cloudflared-watchdog.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared.service
sudo systemctl enable --now cloudflared-watchdog.timer
```

Verification target:
- `cloudflared.service` is `enabled` and `active`.
- `cloudflared-watchdog.timer` is `enabled` and `active`.
- `id cloudflared` succeeds.
- `journalctl` shows a successful tunnel start without config or credential errors.

In setup-only mode, successful startup plus stable root-page reachability is enough. Do not require backend-specific checks.

## 5. Configure Cloudflare tunnel routes and DNS

If the named tunnel already exists, map the public hostnames to it.

CLI route commands:

```bash
cloudflared tunnel route dns ppl-insight-hub-prod1 pplinsighthub.com
cloudflared tunnel route dns ppl-insight-hub-prod1 www.pplinsighthub.com
```

Dashboard equivalent:
- Zero Trust -> Networks -> Tunnels -> `ppl-insight-hub-prod1`
- Add public hostname `pplinsighthub.com` -> service `http://127.0.0.1:80`
- Add public hostname `www.pplinsighthub.com` -> service `http://127.0.0.1:80`

Verification target:
- DNS routes are proxied through the named tunnel.
- Tunnel public hostname entries match the ingress hostnames in `/etc/cloudflared/config.yml`.

## 6. Public cutover verification

From any internet-connected client:

```bash
curl -I https://pplinsighthub.com
curl -I https://www.pplinsighthub.com
curl -I https://pplinsighthub.com/auth/me
curl -I https://pplinsighthub.com/health
```

Expected:
- Frontend routes return `200` or `304`.
- `/auth/me` returns `401` when unauthenticated, confirming backend reachability.
- `/health` returns a successful response through the tunnel.

Setup-only mode verification:

```bash
curl -I https://pplinsighthub.com
curl -I https://www.pplinsighthub.com
```

Expected in setup-only mode:
- Public root page returns `200` or `304`
- Tunnel service remains healthy
- DNS resolves through Cloudflare to the Pi-hosted origin

Do not use `/auth/me` or `/health` as required pass criteria until the backend is actually deployed.

Pi-side verification:

```bash
sudo systemctl status cloudflared --no-pager
sudo journalctl -u cloudflared -n 200 --no-pager
cloudflared tunnel info ppl-insight-hub-prod1
```

## 7. Reboot and watchdog verification

```bash
sudo reboot
```

After reconnecting:

```bash
sudo systemctl is-enabled cloudflared
sudo systemctl is-active cloudflared
sudo systemctl is-enabled cloudflared-watchdog.timer
sudo systemctl is-active cloudflared-watchdog.timer
sudo systemctl list-timers --all | grep cloudflared-watchdog
```

Expected:
- Both units remain `enabled` after reboot.
- Both units are `active`.
- The watchdog timer is scheduled.

## 8. Rollback / abort path

If public routing fails after cutover:

1. Stop the tunnel service on the Pi:

```bash
sudo systemctl stop cloudflared
```

2. Remove or disable the public hostname routes in Cloudflare Zero Trust, or update them away from the broken origin.
3. Re-run local origin checks on the Pi:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -I http://127.0.0.1/
curl -I http://127.0.0.1/auth/me
```

4. Review tunnel logs before retrying:

```bash
sudo journalctl -u cloudflared -n 200 --no-pager
```

Do not change backend or Nginx origin wiring during rollback unless local-origin checks are also failing.

## 9. Security notes

- Keep the tunnel credentials JSON and any token material secret.
- If credentials or token material are exposed, rotate them in Cloudflare before restarting the service.
- Keep origin traffic on local/private HTTP behind the tunnel unless you deliberately implement and validate origin TLS.
- Ensure backend `ALLOWED_HOSTS` and `FRONTEND_ALLOWED_ORIGINS` are already locked down before public cutover.
