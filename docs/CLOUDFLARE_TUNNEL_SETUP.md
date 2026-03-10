# Cloudflare Tunnel Setup (pplinsighthub.com)

This guide configures your existing Cloudflare Tunnel:
- Domain: `pplinsighthub.com`
- Tunnel name: `ppl-insight-hub-prod1`

For full CLI-first workflow (install/login/create/config/DNS/systemd), see:
`docs/cloudflare-tunnel-cli.md`

## 1. Prerequisites

- Nginx is running and serving app on origin port `80`.
- Backend systemd service is running (FastAPI on `127.0.0.1:8000`).
- You already created the tunnel in Cloudflare Zero Trust.

## 2. Install Tunnel Service

You already have this command:

```powershell
cloudflared.exe service install <YOUR_TUNNEL_TOKEN>
```

Run it on the machine that will host the tunnel process.

## 3. Set Public Hostname Route

In Cloudflare Zero Trust dashboard:
- Go to **Networks -> Tunnels -> ppl-insight-hub-prod1**.
- Add Public Hostname:
  - Hostname: `pplinsighthub.com`
  - Service Type: `HTTP`
  - URL:
    - If tunnel is running on the Pi: `http://localhost:80`
    - If tunnel is running on Windows/other host: `http://<PI_LAN_IP>:80`
- Optionally add `www.pplinsighthub.com` to same service.

## 4. DNS

In Cloudflare DNS, ensure CNAME routes are managed by tunnel:
- `pplinsighthub.com` -> tunnel route (proxied)
- `www` -> tunnel route (proxied)

For CLI-based DNS mapping (named tunnel auth required):

```bash
cloudflared tunnel route dns ppl-insight-hub-prod1 pplinsighthub.com
cloudflared tunnel route dns ppl-insight-hub-prod1 www.pplinsighthub.com
```

## 5. Origin Nginx Notes

When using Cloudflare Tunnel, origin TLS certs are optional because Cloudflare terminates TLS at the edge.
- Keep origin on HTTP (`:80`) behind tunnel/private network.
- Do not force HTTP->HTTPS redirect at origin unless your origin receives `X-Forwarded-Proto=https` correctly and you have validated no redirect loops.

## 6. Verify

From public internet:

```bash
curl -I https://pplinsighthub.com
curl -I https://pplinsighthub.com/auth/me
```

Expected:
- Frontend returns `200`/`304`.
- API route returns `401` when unauthenticated (this confirms backend route reachability).

## 7. Troubleshooting Quick Checks

- Tunnel service status (Windows):
```powershell
Get-Service cloudflared
```
- If hostname loads but API fails:
  - Check Nginx route proxy list includes `/auth`, `/players`, `/draft`, etc.
  - Check backend service health:
  ```bash
  sudo systemctl status fantasy-football-backend --no-pager
  ```
- If DNS not resolving:
  - Confirm tunnel public hostname exists in Zero Trust and proxied DNS record is present.

## 8. Security Notes

- Keep tunnel token secret. If it has been exposed, rotate in Cloudflare dashboard and reinstall service.
- Restrict `ALLOWED_HOSTS` and `FRONTEND_ALLOWED_ORIGINS` in backend env for production.
