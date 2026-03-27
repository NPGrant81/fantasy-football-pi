#!/usr/bin/env bash
set -euo pipefail

# Print a Raspberry Pi deploy update plan based on changed files.
#
# Usage:
#   bash scripts/pi_update_plan.sh
#   bash scripts/pi_update_plan.sh origin/main
#
# Optional env:
#   PI_DEPLOY_ROOT=/home/pi/fantasy-football-pi

TARGET_REF="${1:-origin/main}"
REPO_ROOT="${PI_DEPLOY_ROOT:-$(pwd)}"

cd "${REPO_ROOT}"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "ERROR: not inside a git repository: ${REPO_ROOT}" >&2
  exit 1
}

if ! git rev-parse --verify "${TARGET_REF}" >/dev/null 2>&1; then
  echo "INFO: '${TARGET_REF}' not found locally. Running 'git fetch --all --prune'..."
  git fetch --all --prune
fi

git rev-parse --verify "${TARGET_REF}" >/dev/null 2>&1 || {
  echo "ERROR: could not resolve target ref '${TARGET_REF}'" >&2
  exit 1
}

mapfile -t changed_files < <(git diff --name-only HEAD.."${TARGET_REF}")

echo "=== Pi Update Planner ==="
echo "Repo: ${REPO_ROOT}"
echo "Current: $(git rev-parse --short HEAD)"
echo "Target : ${TARGET_REF} ($(git rev-parse --short "${TARGET_REF}"))"

ahead_count=$(git rev-list --count HEAD.."${TARGET_REF}")
if [[ "${ahead_count}" -eq 0 ]]; then
  echo
  echo "No incoming commits from ${TARGET_REF}."
  exit 0
fi

echo
printf 'Incoming commits: %s\n' "${ahead_count}"
git log --oneline HEAD.."${TARGET_REF}"

echo
if [[ ${#changed_files[@]} -eq 0 ]]; then
  echo "No changed files detected in diff range."
  exit 0
fi

echo "Changed files:"
for f in "${changed_files[@]}"; do
  echo "- ${f}"
done

echo

action_backend_deps=0
action_backend_restart=0
action_frontend_build=0
action_nginx_reload=0
action_backend_service_unit=0
action_cloudflared_units=0
action_cloudflared_config=0
action_backup_units=0
action_docs_only=1

for f in "${changed_files[@]}"; do
  case "${f}" in
    backend/requirements*.txt)
      action_backend_deps=1
      action_docs_only=0
      ;;
    backend/*)
      action_backend_restart=1
      action_docs_only=0
      ;;
    frontend/*)
      action_frontend_build=1
      action_docs_only=0
      ;;
    deploy/nginx/*)
      action_nginx_reload=1
      action_docs_only=0
      ;;
    deploy/systemd/fantasy-football-backend.service.example)
      action_backend_service_unit=1
      action_docs_only=0
      ;;
    deploy/systemd/cloudflared*.example)
      action_cloudflared_units=1
      action_docs_only=0
      ;;
    deploy/cloudflared/*)
      action_cloudflared_config=1
      action_docs_only=0
      ;;
    ops/backup/*|deploy/systemd/microsd-db-backup*.example)
      action_backup_units=1
      action_docs_only=0
      ;;
    docs/*)
      ;;
    *)
      action_docs_only=0
      ;;
  esac
done

echo "Recommended commands:"

echo "1) Pull latest code"
echo "   git pull --ff-only"

step=2
if [[ "${action_backend_deps}" -eq 1 ]]; then
  echo "${step}) Reinstall backend dependencies"
  echo "   cd backend && ./venv/bin/pip install -r requirements-lock.txt && cd .."
  ((step++))
fi

if [[ "${action_frontend_build}" -eq 1 ]]; then
  echo "${step}) Rebuild and deploy frontend"
  echo "   cd frontend && npm ci --legacy-peer-deps && npm run build && sudo rsync -av --delete dist/ /var/www/fantasy-football-pi/frontend/dist/ && cd .."
  ((step++))
fi

if [[ "${action_nginx_reload}" -eq 1 ]]; then
  echo "${step}) Apply nginx config template changes"
  echo "   sudo cp deploy/nginx/fantasy-football-pi.conf.example /etc/nginx/sites-available/fantasy-football-pi.conf"
  echo "   sudo nginx -t && sudo systemctl reload nginx"
  ((step++))
fi

if [[ "${action_backend_service_unit}" -eq 1 ]]; then
  echo "${step}) Update backend systemd unit"
  echo "   sudo cp deploy/systemd/fantasy-football-backend.service.example /etc/systemd/system/fantasy-football-backend.service"
  echo "   sudo systemctl daemon-reload && sudo systemctl restart fantasy-football-backend"
  ((step++))
fi

if [[ "${action_cloudflared_units}" -eq 1 ]]; then
  echo "${step}) Update cloudflared systemd units"
  echo "   sudo bash deploy/systemd/install_cloudflared_monitoring.sh"
  ((step++))
fi

if [[ "${action_cloudflared_config}" -eq 1 ]]; then
  echo "${step}) Apply cloudflared config"
  echo "   sudo cp deploy/cloudflared/config.ppl-insight-hub-prod1.example.yml /etc/cloudflared/config.yml"
  echo "   sudo sed -i 's#<tunnel-uuid>#YOUR_TUNNEL_UUID#g' /etc/cloudflared/config.yml"
  echo "   sudo cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate"
  echo "   sudo systemctl restart cloudflared"
  ((step++))
fi

if [[ "${action_backup_units}" -eq 1 ]]; then
  echo "${step}) Update microSD backup automation"
  echo "   sudo install -m 0755 ops/backup/microsd_db_backup.sh /opt/fantasy-football-pi/ops/backup/microsd_db_backup.sh"
  echo "   sudo cp deploy/systemd/microsd-db-backup.service.example /etc/systemd/system/microsd-db-backup.service"
  echo "   sudo cp deploy/systemd/microsd-db-backup.timer.example /etc/systemd/system/microsd-db-backup.timer"
  echo "   sudo systemctl daemon-reload && sudo systemctl enable --now microsd-db-backup.timer"
  ((step++))
fi

if [[ "${action_backend_restart}" -eq 1 || "${action_backend_deps}" -eq 1 ]]; then
  echo "${step}) Restart backend"
  echo "   sudo systemctl restart fantasy-football-backend"
  ((step++))
fi

if [[ "${action_docs_only}" -eq 1 ]]; then
  echo "${step}) Docs-only update detected"
  echo "   No runtime service restart is required."
  ((step++))
fi

echo "${step}) Post-update verification"
echo "   curl -fsS http://127.0.0.1:8000/health"
echo "   sudo systemctl status fantasy-football-backend --no-pager"
echo "   sudo systemctl status nginx --no-pager"
echo "   sudo systemctl status cloudflared --no-pager"
echo "   sudo systemctl status cloudflared-watchdog.timer --no-pager"
echo "   sudo systemctl list-timers --all | grep microsd-db-backup"
