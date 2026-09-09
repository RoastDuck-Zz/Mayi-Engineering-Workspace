#!/usr/bin/env bash
set -euo pipefail

INTERFACE="eth0"
CONNECTION="robotdog-wired"
WIFI_INTERFACE="wlan0"
SYS_CLASS_NET="${MYMOOO_SYS_CLASS_NET:-/sys/class/net}"
FORCE=no
INTERFACE_SET=no

usage() {
  echo "Usage: $0 [eth0] [--force]" >&2
}

for argument in "$@"; do
  case "${argument}" in
    --force)
      FORCE=yes
      ;;
    --*)
      usage
      exit 2
      ;;
    *)
      if [[ "${INTERFACE_SET}" == "yes" ]]; then
        usage
        exit 2
      fi
      INTERFACE="${argument}"
      INTERFACE_SET=yes
      ;;
  esac
done

if ! [[ "${INTERFACE}" =~ ^[a-zA-Z0-9._-]+$ ]]; then
  usage
  exit 2
fi

management_not_ready() {
  echo "ERROR: Wi-Fi management channel is not ready." >&2
  echo "Refusing to reconfigure ${INTERFACE} because this may terminate SSH access." >&2
  exit 1
}

if [[ ! -d "${SYS_CLASS_NET}/${WIFI_INTERFACE}" ]]; then
  management_not_ready
fi

if ! command -v ip >/dev/null 2>&1 || \
   ! ip link show dev "${WIFI_INTERFACE}" 2>/dev/null | grep -Eq '<[^>]*UP([,>])'; then
  management_not_ready
fi

if ! ip -4 -o addr show dev "${WIFI_INTERFACE}" scope global 2>/dev/null | grep -q ' inet '; then
  management_not_ready
fi

if ! ip route show default 2>/dev/null | grep -Eq "(^|[[:space:]])dev ${WIFI_INTERFACE}([[:space:]]|$)"; then
  management_not_ready
fi

if ! command -v systemctl >/dev/null 2>&1 || \
   ! systemctl is-active --quiet ssh.service; then
  management_not_ready
fi

if [[ -n "${SSH_CONNECTION:-}" ]]; then
  read -r _ssh_client _ssh_client_port ssh_local_address _ssh_server_port <<< "${SSH_CONNECTION}"
  while read -r interface_address; do
    if [[ "${ssh_local_address}" == "${interface_address%/*}" ]]; then
      if [[ "${FORCE}" != "yes" ]]; then
        echo "Current SSH session appears to be using ${INTERFACE}." >&2
        echo "Open and verify a separate Wi-Fi session first: ssh guidedog@<wlan0-ip>" >&2
        echo "Then rerun from that session, or use --force only if you accept losing SSH access." >&2
        exit 1
      fi
      echo "WARNING: --force is bypassing the current ${INTERFACE} SSH-session guard." >&2
    fi
  done < <(ip -4 -o addr show dev "${INTERFACE}" scope global 2>/dev/null | awk '{print $4}')
fi

if ! command -v nmcli >/dev/null 2>&1; then
  echo "未找到 nmcli，请在 Raspberry Pi 网络设置中手动配置 ${INTERFACE} 为 10.21.20.2/24"
  exit 1
fi

if [[ ! -d "${SYS_CLASS_NET}/${INTERFACE}" ]]; then
  echo "网卡不存在: ${INTERFACE}"
  exit 1
fi

if nmcli -t -f NAME connection show | grep -Fxq "$CONNECTION"; then
  sudo nmcli connection modify "$CONNECTION" \
    connection.interface-name "$INTERFACE" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100 \
    ipv4.method manual \
    ipv4.addresses 10.21.20.2/24 \
    ipv4.gateway "" \
    ipv4.dns "" \
    ipv4.never-default yes \
    ipv6.method disabled
else
  sudo nmcli connection add type ethernet \
    ifname "$INTERFACE" \
    con-name "$CONNECTION" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100 \
    ipv4.method manual \
    ipv4.addresses 10.21.20.2/24 \
    ipv4.never-default yes \
    ipv6.method disabled
fi

if [[ "$(cat "${SYS_CLASS_NET}/${INTERFACE}/carrier" 2>/dev/null || true)" != "1" ]]; then
  echo "已保存 ${CONNECTION}: ${INTERFACE}=10.21.20.2/24；插入 Mymooo 网线后将自动连接"
  exit 0
fi

sudo nmcli connection up "$CONNECTION"
ip -br addr show "${INTERFACE}"
ip route get 10.21.20.1
