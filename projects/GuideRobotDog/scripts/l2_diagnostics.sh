#!/usr/bin/env bash
# Inventory only; missing tools/privilege are reported, never installed automatically.
set -u
if [[ $(uname -s) != Linux ]]; then echo 'ERROR: run on the actual Raspberry Pi'; exit 2; fi
run() { printf '\n###'; printf ' %q' "$@"; printf '\n'; "$@"; local rc=$?; echo "exit_status=$rc"; }
run date -u +%FT%TZ
run uname -a
run cat /etc/os-release
run arch
run ip addr
run ip link
run ip route
run lsusb
run lsusb -t
run lspci
echo '### ROS environment'
if command -v ros2; then run ros2 --version; else echo 'ros2 not found in current PATH'; fi
printenv | grep '^ROS' || true
ls -d /opt/ros/* 2>/dev/null || true
echo '### All physical network devices (none automatically declared L2)'
for path in /sys/class/net/*; do
  [[ -e $path/device ]] || continue
  name=${path##*/}
  run cat "$path/address"
  run readlink -f "$path/device"
  run ip -s link show dev "$name"
  if command -v ethtool >/dev/null; then run ethtool "$name"; run ethtool -i "$name"; fi
done
run ip neigh
echo '### Kernel USB/link/power evidence'
if (( EUID == 0 )); then
  dmesg --ctime | grep -Ei 'usb|ether|r8152|r8153|ax88179|link|disconnect|reset|voltage|power'
elif sudo -n true 2>/dev/null; then
  sudo -n dmesg --ctime | grep -Ei 'usb|ether|r8152|r8153|ax88179|link|disconnect|reset|voltage|power'
else
  echo 'Kernel log needs sudo -v; falling back to accessible journal'
  journalctl -k -b --no-pager | grep -Ei 'usb|ether|r8152|r8153|ax88179|link|disconnect|reset|voltage|power'
fi
echo '### SDK discovery (does not prove provenance or installation)'
find "$HOME" -maxdepth 4 -iname '*unilidar*' 2>/dev/null
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
if [[ -f $root/config/sdk.lock.json ]]; then
  echo '### Recorded SDK provenance (archive checkout has no active git branch)'
  cat "$root/config/sdk.lock.json"
fi
if [[ -f $root/unilidar_sdk2-v2.0.10.zip ]]; then
  run sha256sum "$root/unilidar_sdk2-v2.0.10.zip"
fi
if [[ -n ${L2_SDK_DIR:-} ]]; then
  run git -C "$L2_SDK_DIR" remote -v
  run git -C "$L2_SDK_DIR" rev-parse HEAD
  run git -C "$L2_SDK_DIR" branch --show-current
  run git -C "$L2_SDK_DIR" describe --tags --always --dirty
else echo 'L2_SDK_DIR unset: no git checkout inspection; see archive lock/hash above if present'; fi
if [[ -n ${L2_INTERFACE:-} && -n ${L2_IP:-} ]]; then
  bash "$(dirname "$0")/l2_network_test.sh"
  exit $?
fi
echo 'BLOCKED: L2_INTERFACE / L2_IP not confirmed; L2 ping and UDP tests skipped.'
exit 3
