#!/usr/bin/env bash
# Read-only descriptor queries. Use --private only for local evidence.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$root/scripts/l2_usb_diagnostics.py" "$@"
