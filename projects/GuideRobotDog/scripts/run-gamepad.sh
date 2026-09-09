#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "${PROJECT_DIR}/.venv/bin/python" ]]; then
  echo "Missing project .venv; run scripts/setup-pi.sh first" >&2
  exit 1
fi
if [[ -z "${MYMOOO_PIN:-${ROBOTDOG_PIN:-}}" ]]; then
  echo "Missing control PIN in /etc/robotdog-web.env" >&2
  exit 1
fi
cd "${PROJECT_DIR}"
exec "${PROJECT_DIR}/.venv/bin/python" -u gamepad.py --control --standby
