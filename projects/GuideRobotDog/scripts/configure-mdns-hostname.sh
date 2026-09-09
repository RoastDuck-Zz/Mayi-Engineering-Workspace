#!/usr/bin/env bash
set -euo pipefail

MDNS_HOSTNAME="${1:-mymooo}"
WIFI_INTERFACE="${2:-wlan0}"

if ! [[ "$MDNS_HOSTNAME" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; then
  echo "主机名必须由小写字母、数字和中划线组成，长度不超过 63" >&2
  exit 1
fi

if ! [[ "$WIFI_INTERFACE" =~ ^[a-zA-Z0-9._-]+$ ]] || [[ ! -d "/sys/class/net/${WIFI_INTERFACE}" ]]; then
  echo "WiFi 接口不存在或名称无效: ${WIFI_INTERFACE}" >&2
  exit 1
fi

if ! command -v hostnamectl >/dev/null 2>&1; then
  echo "系统缺少 hostnamectl" >&2
  exit 1
fi

if ! systemctl list-unit-files avahi-daemon.service >/dev/null 2>&1; then
  echo "系统未安装 avahi-daemon，无法提供 .local 固定地址" >&2
  exit 1
fi

OLD_HOSTNAME="$(hostnamectl --static)"
HOSTS_LINE="127.0.1.1 ${MDNS_HOSTNAME}"
if [[ -n "$OLD_HOSTNAME" && "$OLD_HOSTNAME" != "$MDNS_HOSTNAME" ]]; then
  HOSTS_LINE+=" ${OLD_HOSTNAME}"
fi

sudo hostnamectl set-hostname "$MDNS_HOSTNAME"
if grep -Eq '^127\.0\.1\.1([[:space:]]|$)' /etc/hosts; then
  sudo sed -i -E "s/^127\.0\.1\.1([[:space:]]+).*/${HOSTS_LINE}/" /etc/hosts
else
  printf '%s\n' "$HOSTS_LINE" | sudo tee -a /etc/hosts >/dev/null
fi

# Only publish the operator-facing WiFi address.  The separate robot Ethernet
# address (10.21.20.2) is intentionally unreachable from phones and must not
# be returned for mymooo.local.
if grep -Eq '^#?allow-interfaces=' /etc/avahi/avahi-daemon.conf; then
  sudo sed -i -E \
    "s/^#?allow-interfaces=.*/allow-interfaces=${WIFI_INTERFACE}/" \
    /etc/avahi/avahi-daemon.conf
else
  sudo sed -i "/^\[server\]$/a allow-interfaces=${WIFI_INTERFACE}" \
    /etc/avahi/avahi-daemon.conf
fi

sudo systemctl enable avahi-daemon.service
sudo systemctl restart avahi-daemon.service

echo "固定控制台地址已启用: http://${MDNS_HOSTNAME}.local:8088"
echo "mDNS 仅通过 WiFi 接口发布: ${WIFI_INTERFACE}"
echo "数字 IP 仍可继续使用；切换 WiFi 后优先使用上述 .local 地址。"
