#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
SDK_DIR="${1:-${PROJECT_DIR}/vendor/bpx_sdk_open}"
BPX_SDK_REF="${BPX_SDK_REF:-}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python virtual environment not found: ${PROJECT_DIR}/.venv" >&2
  echo "Run scripts/setup-pi.sh first." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y git build-essential python3-dev

if [[ ! -d "${SDK_DIR}/.git" ]]; then
  git clone https://github.com/mirrormerobotics/bpx_sdk_open.git "${SDK_DIR}"
fi

if [[ -n "${BPX_SDK_REF}" ]]; then
  git -C "${SDK_DIR}" fetch origin "${BPX_SDK_REF}"
  git -C "${SDK_DIR}" checkout --detach FETCH_HEAD
else
  echo "WARNING: UNPINNED SDK VERSION; set BPX_SDK_REF to a reviewed tag or commit." >&2
  git -C "${SDK_DIR}" fetch --prune origin
  DEFAULT_BRANCH="$(git -C "${SDK_DIR}" symbolic-ref --short refs/remotes/origin/HEAD)"
  DEFAULT_BRANCH="${DEFAULT_BRANCH#origin/}"
  git -C "${SDK_DIR}" checkout "${DEFAULT_BRANCH}"
  git -C "${SDK_DIR}" pull --ff-only origin "${DEFAULT_BRANCH}"
fi

"${PROJECT_DIR}/.venv/bin/python" -m pip install "${SDK_DIR}"
"${PYTHON_BIN}" -c "import bpx_sdk; print('bpx_sdk installed in project virtual environment')"
