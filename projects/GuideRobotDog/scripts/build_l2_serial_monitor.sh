#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(uname -s)" != Linux ]]; then
    echo 'NOT READY: Linux termios is required' >&2
    exit 2
fi
compiler="${CXX:-g++}"
if ! command -v "$compiler" >/dev/null 2>&1; then
    echo 'NOT READY: C++17 compiler unavailable; no packages were installed' >&2
    exit 2
fi
if (( $# > 1 )); then echo 'usage: build_l2_serial_monitor.sh [output-binary]' >&2; exit 2; fi
output="${1:-$root/build/l2_serial_monitor}"
mkdir -p -- "$(dirname -- "$output")"
src="$root/native/l2_serial"
"$compiler" -std=c++17 -O2 -Wall -Wextra -Werror \
    "$src/serial_transport.cpp" "$src/frame_assembler.cpp" \
    "$src/l2_packet_decoder.cpp" "$src/timestamp_analyzer.cpp" \
    "$src/diagnostic_report.cpp" "$src/l2_serial_monitor.cpp" -o "$output"
echo "Built $output (no hardware accessed)"
