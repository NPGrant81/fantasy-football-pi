#!/usr/bin/env bash
set -euo pipefail

# Install cloudflared monitoring systemd units for Raspberry Pi deployment.
# Usage:
#   sudo bash deploy/systemd/install_cloudflared_monitoring.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

if [[ "${EUID}" -ne 0 ]]; then
	echo "Run this script as root (use sudo)."
	exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
	echo "cloudflared binary not found in PATH. Install cloudflared first."
	exit 1
fi

if [[ ! -f "/etc/cloudflared/config.yml" ]]; then
	echo "Missing /etc/cloudflared/config.yml. Create tunnel config before installing units."
	exit 1
fi

if ! getent group cloudflared >/dev/null 2>&1; then
	groupadd --system cloudflared
fi

if ! getent passwd cloudflared >/dev/null 2>&1; then
	useradd --system --gid cloudflared --home-dir /var/lib/cloudflared --create-home --shell /usr/sbin/nologin cloudflared
fi

install -d -m 0755 -o cloudflared -g cloudflared /etc/cloudflared
install -d -m 0755 -o cloudflared -g cloudflared /var/log/cloudflared

install -m 0644 "${SCRIPT_DIR}/cloudflared.service.example" "${SYSTEMD_DIR}/cloudflared.service"
install -m 0644 "${SCRIPT_DIR}/cloudflared-watchdog.service.example" "${SYSTEMD_DIR}/cloudflared-watchdog.service"
install -m 0644 "${SCRIPT_DIR}/cloudflared-watchdog.timer.example" "${SYSTEMD_DIR}/cloudflared-watchdog.timer"

systemctl daemon-reload
systemctl enable --now cloudflared.service
systemctl enable --now cloudflared-watchdog.timer

printf "\nCloudflared monitoring units installed.\n"
printf "Check status with:\n"
printf "  systemctl status cloudflared --no-pager\n"
printf "  systemctl status cloudflared-watchdog.timer --no-pager\n"
printf "  journalctl -u cloudflared -n 100 --no-pager\n"
