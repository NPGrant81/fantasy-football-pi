#!/usr/bin/env bash
set -euo pipefail

# Install cloudflared monitoring systemd units for Raspberry Pi deployment.
# Usage:
#   sudo bash deploy/systemd/install_cloudflared_monitoring.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

if ! getent group cloudflared >/dev/null; then
	groupadd --system cloudflared
fi

if ! id -u cloudflared >/dev/null 2>&1; then
	useradd --system --no-create-home --gid cloudflared --home-dir /nonexistent --shell /usr/sbin/nologin cloudflared
fi

install -d -m 0750 -o root -g cloudflared /etc/cloudflared

install -m 0644 "${SCRIPT_DIR}/cloudflared.service.example" "${SYSTEMD_DIR}/cloudflared.service"
install -m 0644 "${SCRIPT_DIR}/cloudflared-watchdog.service.example" "${SYSTEMD_DIR}/cloudflared-watchdog.service"
install -m 0644 "${SCRIPT_DIR}/cloudflared-watchdog.timer.example" "${SYSTEMD_DIR}/cloudflared-watchdog.timer"

systemctl daemon-reload
systemctl enable --now cloudflared.service
systemctl enable --now cloudflared-watchdog.timer

printf "\nCloudflared monitoring units installed.\n"
printf "Cloudflared service user/group ensured.\n"
printf "Check status with:\n"
printf "  systemctl status cloudflared --no-pager\n"
printf "  systemctl status cloudflared-watchdog.timer --no-pager\n"
printf "  journalctl -u cloudflared -n 100 --no-pager\n"
