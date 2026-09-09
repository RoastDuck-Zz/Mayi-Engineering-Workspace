#!/usr/bin/env bash
# Read-only network probe. No automatic interface selection or address changes.
set -u
interface=${1:-${L2_INTERFACE:-}}
lidar_ip=${2:-${L2_IP:-}}
duration=${L2_CAPTURE_SECONDS:-10}
if [[ $(uname -s) != Linux ]]; then echo 'ERROR: run on the actual Linux host'; exit 2; fi
if [[ ! $interface =~ ^[a-zA-Z0-9_.:-]+$ || ! -d /sys/class/net/$interface || -z $lidar_ip ]]; then
  echo 'Usage: l2_network_test.sh CONFIRMED_INTERFACE CONFIRMED_L2_IPV4'
  echo 'Or set L2_INTERFACE and L2_IP. No interface/IP is assumed.'
  exit 2
fi
if [[ ! $lidar_ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ || ! $duration =~ ^[0-9]+$ ]] || (( duration < 1 || duration > 120 )); then
  echo 'ERROR: expected IPv4 and capture duration 1..120 seconds'; exit 2
fi
IFS=. read -r -a octets <<< "$lidar_ip"
for octet in "${octets[@]}"; do
  if (( 10#$octet > 255 )); then echo 'ERROR: invalid IPv4'; exit 2; fi
done
echo "UTC=$(date -u +%FT%TZ) interface=$interface L2_IP=$lidar_ip"
ip -s link show dev "$interface"
ip addr show dev "$interface"
ip route show
if command -v ethtool >/dev/null; then ethtool "$interface"; ethtool -i "$interface"; fi
if [[ $(cat "/sys/class/net/$interface/carrier" 2>/dev/null) != 1 ]]; then
  echo 'BLOCKED: no carrier; no ping or capture attempted'; exit 3
fi
route=$(ip -4 route get "$lidar_ip" oif "$interface" 2>&1) || { echo "$route"; exit 3; }
echo "$route"
if [[ " $route " == *' via '* || " $route " != *" dev $interface "* ]]; then
  echo 'BLOCKED: require a direct route on the confirmed isolated L2 interface'; exit 3
fi
ping -n -I "$interface" -c 4 -W 1 "$lidar_ip"
echo "ping_exit=$? (ICMP failure alone does not diagnose a failed LiDAR)"
ip neigh show dev "$interface"
if ! command -v tcpdump >/dev/null; then echo 'BLOCKED: tcpdump missing'; exit 4; fi
priv=()
if (( EUID != 0 )); then
  if ! sudo -n true 2>/dev/null; then echo 'BLOCKED: run sudo -v first for capture'; exit 4; fi
  priv=(sudo -n)
fi
capture=$(mktemp) || exit 4
errors=$(mktemp) || { rm -f -- "$capture"; exit 4; }
trap 'rm -f -- "$capture" "$errors"' EXIT
echo "Capturing inbound UDP from $lidar_ip for ${duration}s; no payload is saved."
"${priv[@]}" timeout -s INT "$duration" tcpdump -p -Q in -nn -l -tt -i "$interface" "udp and src host $lidar_ip" >"$capture" 2>"$errors"
status=$?
cat "$errors"
if (( status != 0 && status != 124 )); then echo "capture_error=$status"; exit 4; fi
awk -v seconds="$duration" '
  /^[0-9]+\.[0-9]+ / {n++; second=int($1); buckets[second]++; if(n>1 && $1-last>gap)gap=$1-last; last=$1}
  END {printf "packets=%d average_packets_per_second=%.3f max_observed_interpacket_gap_seconds=%.6f\n",n,n/seconds,gap;
       for(s in buckets)printf "epoch_second=%s packets=%d\n",s,buckets[s];
       print "Capture observations only: not SDK frame loss or a 60-second stability acceptance."}
' "$capture"
if [[ ! -s $capture ]]; then echo 'NO_UDP_OBSERVED: check ARP, target IP/port and device state'; exit 5; fi
