#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=()
else
  SUDO=(sudo)
fi

"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y python3 python3-venv python3-pip

if [[ ! -d "${PROJECT_DIR}/.venv" ]]; then
  python3 -m venv "${PROJECT_DIR}/.venv"
fi

"${PROJECT_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${PROJECT_DIR}/.venv/bin/python" -m pip install -r "${PROJECT_DIR}/requirements-base.txt"

chmod +x "${PROJECT_DIR}"/scripts/*.sh "${PROJECT_DIR}/dogstatus"
echo "Base Raspberry Pi environment ready: ${PROJECT_DIR}/.venv"
echo "Hardware dependencies were not installed. Mock mode is the safe default."
