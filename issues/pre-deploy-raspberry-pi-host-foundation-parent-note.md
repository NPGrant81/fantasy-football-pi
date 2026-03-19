Parent issue note draft for #79

Pre-deploy host foundation update complete on Raspberry Pi (2026-03-18).

Completed now:
- Installed missing baseline packages: `ufw`, `fail2ban`, `tmux`
- Confirmed existing baseline packages were present: git, curl, build-essential, nodejs/npm, python3/pip/venv, nginx, htop, logrotate, net-tools
- Enabled UFW with safe baseline rules:
  - allow OpenSSH (22)
  - allow Nginx Full (80/443)
  - default deny incoming / allow outgoing
- Enabled/started fail2ban and nginx
- Verified fail2ban jail list includes `sshd`

Verification commands/results:
- `sudo ufw status verbose` => active; expected rules present
- `systemctl is-enabled fail2ban nginx` => enabled
- `systemctl is-active fail2ban nginx` => active
- `sudo fail2ban-client status` => jail list: sshd

Version snapshot:
- node v20.19.2
- npm 9.2.0
- python 3.13.5
- pip 25.1.1
- nginx 1.26.3
- tmux 3.5a

Deferred (app-coupled, intentionally not done yet):
- Final Nginx site + TLS cert wiring
- Cloudflared prod credentials + service cutover
- Backend production env/secrets finalization
- Backup timer activation against final DB target

Child issue tracking this execution:
- Pre-Deploy Raspberry Pi Host Foundation Checklist (Packages, Hardening, Service Readiness)
