#!/usr/bin/env bash
set -eu
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
sdk=${L2_SDK_DIR:-$root/vendor/unilidar_sdk2-2.0.10/unitree_lidar_sdk}
cpu=$(uname -m)
[[ -f $sdk/lib/$cpu/libunilidar_sdk2.a ]] || { echo "Missing official library for $cpu: $sdk"; exit 2; }
mkdir -p "$root/reports"
cmake -S "$sdk" -B "$root/build-official"
cmake --build "$root/build-official" --target example_lidar_udp -j2
g++ -O2 -std=c++17 -Wall -Wextra -I "$sdk/include" "$root/native/l2_monitor.cpp" \
  "$sdk/lib/$cpu/libunilidar_sdk2.a" -pthread -o "$root/l2_monitor"
echo 'Built only. Vendor example sets mode/resets device; do not run unchanged.'
echo 'Monitor preserves raw timestamps. Known vendor closeUDP crash is NOT fixed.'
