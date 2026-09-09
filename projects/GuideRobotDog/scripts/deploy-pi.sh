#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="/home/guidedog/robotdog-control"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
START_SERVICE=no

if [[ "${1:-}" == "--start" ]]; then
  START_SERVICE=yes
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--start]" >&2
  exit 2
fi

if [[ "${PROJECT_DIR}" != "${DEPLOY_DIR}" ]]; then
  echo "Upload this directory to ${DEPLOY_DIR} before running deploy-pi.sh" >&2
  exit 1
fi

if [[ "$(id -un)" != "guidedog" ]]; then
  echo "Run this script as the guidedog user." >&2
  exit 1
fi

bash "${PROJECT_DIR}/scripts/setup-pi.sh"
sudo install -m 0644 "${PROJECT_DIR}/robotdog-web.service" /etc/systemd/system/robotdog-web.service
sudo systemctl daemon-reload
sudo systemctl enable robotdog-web.service

if [[ "${START_SERVICE}" == "yes" ]]; then
  sudo systemctl restart robotdog-web.service
  sudo systemctl --no-pager --full status robotdog-web.service
else
  echo "Mock service installed and enabled but not started."
  echo "After setting MYMOOO_PIN (or legacy ROBOTDOG_PIN), run: $0 --start"
fi
