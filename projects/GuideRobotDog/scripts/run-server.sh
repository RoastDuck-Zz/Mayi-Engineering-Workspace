#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "${SCRIPT_DIR}" == "${SCRIPT_PATH}" ]]; then
  SCRIPT_DIR="."
fi
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python virtual environment not found: ${PROJECT_DIR}/.venv" >&2
  echo "Run scripts/setup-pi.sh first." >&2
  exit 1
fi

cd "${PROJECT_DIR}"
exec "${PYTHON_BIN}" server.py "$@"
