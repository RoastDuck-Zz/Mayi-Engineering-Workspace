#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $(uname -s) == Linux ]] || { echo 'NOT READY: Linux required' >&2; exit 2; }
out="${1:-$root/build}"
mkdir -p -- "$out"
src="$root/native"
g++ -std=c++17 -O2 -Wall -Wextra -Werror -I"$src/l2_serial" -I"$src/l2_ethernet" \
  "$src/l2_ethernet/l2_udp_monitor.cpp" "$src/l2_ethernet/udp_protocol.cpp" \
  "$src/l2_serial/frame_assembler.cpp" "$src/l2_serial/l2_packet_decoder.cpp" \
  "$src/l2_serial/timestamp_analyzer.cpp" -o "$out/l2_udp_monitor"
g++ -std=c++17 -O2 -Wall -Wextra -Werror -I"$src/l2_serial" -I"$src/l2_ethernet" \
  "$src/l2_ethernet/l2_udp_capture.cpp" -o "$out/l2_udp_capture"
g++ -std=c++17 -O2 -Wall -Wextra -Werror -I"$src/l2_serial" -I"$src/l2_ethernet" \
  "$src/l2_ethernet/l2_udp_replay.cpp" "$src/l2_ethernet/udp_protocol.cpp" \
  "$src/l2_serial/frame_assembler.cpp" "$src/l2_serial/l2_packet_decoder.cpp" \
  "$src/l2_serial/timestamp_analyzer.cpp" -o "$out/l2_udp_replay"
echo 'Built l2_udp_monitor; no hardware accessed'
