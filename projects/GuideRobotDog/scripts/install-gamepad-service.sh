#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${PROJECT_DIR}" != /home/guidedog/robotdog-control ]]; then
  echo "Deploy project to /home/guidedog/robotdog-control first" >&2
  exit 1
fi
"${PROJECT_DIR}/.venv/bin/python" -c 'import evdev'
sudo test -f /etc/robotdog-web.env
sudo install -m 0644 "${PROJECT_DIR}/robotdog-gamepad.service" /etc/systemd/system/robotdog-gamepad.service
sudo systemctl daemon-reload
# Enable on boot only. Operator can start standby with --start.
sudo systemctl enable robotdog-gamepad.service
if [[ "${1:-}" == --start ]]; then
  sudo systemctl start robotdog-gamepad.service
fi
