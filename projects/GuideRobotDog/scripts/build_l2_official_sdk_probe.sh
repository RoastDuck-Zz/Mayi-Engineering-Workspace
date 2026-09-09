#!/usr/bin/env bash
set -eu
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
sdk=${L2_SDK_DIR:-$root/vendor/unilidar_sdk2-2.0.10/unitree_lidar_sdk}
cpu=$(uname -m)
lib="$sdk/lib/$cpu/libunilidar_sdk2.a"
[[ -f "$lib" ]] || { echo "Missing pinned Unitree SDK library: $lib"; exit 2; }
mkdir -p "$root/build-official"
g++ -O2 -std=c++17 -Wall -Wextra -Werror -I "$sdk/include" "$root/native/l2_official_sdk_probe.cpp" "$lib" -pthread -o "$root/build-official/l2_official_sdk_probe"
echo "Built l2_official_sdk_probe against Unitree SDK v2.0.10; receive path only"
