"""Compatibility entrypoint for the corrected multi-frame UDP analyzer."""
import json
import sys
from l2_wire_analyzer import analyze, live

if len(sys.argv) != 5:
    raise SystemExit("Usage: l2_udp_probe.py HOST_IP LIDAR_IP SECONDS OUTPUT_PREFIX")
host, lidar, duration, output = sys.argv[1:]
duration = float(duration)
if not 1 <= duration <= 120:
    raise SystemExit("duration must be 1..120 seconds")
print(json.dumps(analyze(live(host, lidar, duration), output), indent=2))
