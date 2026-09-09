"""Validate a real monitor summary; never generates or simulates sensor data."""
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    s = json.load(stream)
with open(sys.argv[2], encoding="utf-8") as stream:
    process_exit = int(stream.read())
checks = {
    "process_exit": process_exit == 0,
    "duration": s["duration"] >= 60,
    "clouds": s["cloud"]["count"] > 100,
    "imu": s["imu"]["count"] > 100,
    "finite_points": s["invalid_points"] == 0,
    "nonempty_clouds": s["empty_clouds"] == 0,
    "finite_imu": s["imu"]["count"] > 0 and s["invalid_imu"] == 0,
}
for name in ("cloud", "imu", "raw_lidar"):
    t = s[name]
    checks[name + "_clock"] = 0.98 <= t["clock_ratio"] <= 1.02 and t["backward"] == 0
    checks[name + "_continuity"] = (t["count"] > 1 and t["max_gap"] < 1 and t["sequence_gaps"] == 0
                                   and t["sequence_resets"] == 0 and t["duplicates"] == 0)
for name, ok in checks.items():
    print(f"{'PASS' if ok else 'FAIL'} {name}")
sys.exit(0 if all(checks.values()) else 1)
