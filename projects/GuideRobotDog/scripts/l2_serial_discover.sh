#!/usr/bin/env bash
# Metadata only: never open/read/write a tty or issue a device command.
set -u
if [[ $# != 0 || $(uname -s) != Linux ]]; then
  echo 'Usage: bash scripts/l2_serial_discover.sh (on the actual Linux Raspberry Pi)'
  exit 2
fi

dev_root=${L2_DISCOVERY_DEV_ROOT:-/dev}
sys_tty_root=${L2_DISCOVERY_SYS_TTY_ROOT:-/sys/class/tty}
incomplete=0
run() {
  printf '\n###'; printf ' %q' "$@"; printf '\n'
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "UNAVAILABLE: $1"
    incomplete=1
    return
  fi
  "$@"
  local rc=$?
  echo "exit_status=$rc"
  if (( rc != 0 )); then incomplete=1; fi
}

echo 'L2 serial discovery: read-only metadata inventory; no device is selected.'
echo 'Output may contain USB serial numbers/topology; keep raw output private.'
if [[ $dev_root != /dev || $sys_tty_root != /sys/class/tty ]]; then
  echo 'OVERRIDDEN inventory roots: offline/fixture metadata is not Pi evidence.'
fi
printf 'device_root=%s\nsys_tty_root=%s\n' "$dev_root" "$sys_tty_root"
if [[ ! -d $dev_root || ! -d $sys_tty_root ]]; then
  echo 'UNAVAILABLE: inventory directory'
  incomplete=1
fi
run lsusb
run lsusb -t

shopt -s nullglob
candidates=("$dev_root"/ttyACM* "$dev_root"/ttyUSB*)
printf '\ncandidate_count=%s\n' "${#candidates[@]}"
for device in "${candidates[@]}"; do
  name=${device##*/}
  printf '\nCandidate (identity unverified): %s\n' "$device"
  run ls -ld -- "$device"
  run udevadm info --query=property --name="$device"
  run udevadm info --attribute-walk --name="$device"
  run readlink -e -- "$sys_tty_root/$name/device"
done

echo 'Persistent names (existing only; none created):'
for path in "$dev_root/unitree_l2" "$dev_root/serial/by-id" "$dev_root/serial/by-path"; do
  if [[ -e $path || -L $path ]]; then
    run ls -ld -- "$path"
    if [[ -d $path ]]; then run ls -l -- "$path"; fi
  else
    printf 'not present: %s\n' "$path"
  fi
done

echo 'L2 identity: UNKNOWN (operator must correlate physical adapter and metadata)'
echo 'Current work mode: UNKNOWN'
echo 'Serial SDK runtime: NOT RUN'
echo 'READY FOR ROS2: NO'
echo 'Exit 0 means inventory completed with candidates, never L2 acceptance.'
if (( incomplete )); then exit 4; fi
if (( ${#candidates[@]} == 0 )); then exit 3; fi
exit 0
