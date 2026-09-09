#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $(uname -s) == Linux ]] || { echo 'NOT READY: Linux required' >&2; exit 2; }
(( $# <= 1 )) || { echo 'usage: build_l2_serial_integrity.sh [output-directory]' >&2; exit 2; }
compiler="${CXX:-g++}"
command -v "$compiler" >/dev/null || { echo 'NOT READY: compiler missing' >&2; exit 2; }
out="${1:-$root/build}"
mkdir -p -- "$out"
src="$root/native/l2_serial"
common=("$src/frame_assembler.cpp" "$src/l2_packet_decoder.cpp" "$src/timestamp_analyzer.cpp" "$src/diagnostic_report.cpp")
"$compiler" -std=c++17 -O2 -Wall -Wextra -Werror "$src/l2_serial_capture.cpp" "$src/serial_transport.cpp" "${common[@]}" -o "$out/l2_serial_capture"
"$compiler" -std=c++17 -O2 -Wall -Wextra -Werror "$src/l2_serial_replay.cpp" "${common[@]}" -o "$out/l2_serial_replay"
echo 'Built capture/replay; no hardware accessed'
