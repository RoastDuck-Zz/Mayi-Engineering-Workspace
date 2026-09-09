#!/usr/bin/env bash
set -u

WIFI_INTERFACE="${1:-wlan0}"
ETHERNET_INTERFACE="${2:-eth0}"
SYS_CLASS_NET="${MYMOOO_SYS_CLASS_NET:-/sys/class/net}"

show_link() {
  local interface="$1"
  if [[ ! -d "${SYS_CLASS_NET}/${interface}" ]] || ! command -v ip >/dev/null 2>&1; then
    echo "${interface} unavailable"
    return
  fi
  ip -br link show dev "${interface}" 2>/dev/null || echo "${interface} unavailable"
  ip -br -4 addr show dev "${interface}" 2>/dev/null || true
}

echo "=== Mymooo Management Link Check ==="
echo
echo "Hostname:"
hostname 2>/dev/null || echo "unavailable"
echo
echo "Architecture:"
uname -m 2>/dev/null || echo "unavailable"
echo
echo "Wi-Fi:"
show_link "${WIFI_INTERFACE}"
echo
echo "Default route:"
if command -v ip >/dev/null 2>&1; then
  ip route show default 2>/dev/null || echo "unavailable"
else
  echo "unavailable"
fi
echo
echo "SSH:"
if command -v systemctl >/dev/null 2>&1; then
  SSH_STATE="$(systemctl is-active ssh.service 2>/dev/null || true)"
  echo "${SSH_STATE:-inactive}"
else
  echo "unavailable"
fi
echo
echo "Web:"
if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -Eq ':8088([[:space:]]|$)'; then
  echo "8088 listening"
else
  echo "8088 not listening"
fi
echo
echo "Ethernet:"
show_link "${ETHERNET_INTERFACE}"
echo
echo "IMPORTANT:"
echo "Do not reconfigure eth0 until Wi-Fi SSH is verified."
