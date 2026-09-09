#!/usr/bin/env bash
set -eu
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
sdk=${L2_SDK_DIR:-$root/vendor/unilidar_sdk2-2.0.10/unitree_lidar_sdk}
cpu=$(uname -m)
for name in l2_monitor_safe l2_close_repro l2_protocol_layout l2_mode_once l2_sync_once; do
  g++ -O2 -g -std=c++17 -Wall -Wextra -I "$sdk/include" "$root/native/$name.cpp" \
    "$sdk/lib/$cpu/libunilidar_sdk2.a" -pthread -o "$root/$name"
done
echo 'Build only. No device command has been run.'
echo 'Mode/reset/sync tools require explicit authorization flags; normal monitoring uses l2_monitor_safe.'
