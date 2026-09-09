# L2 Serial Core v1

Receive foundation for lidar obstacle avoidance and lidar target following.
Exports `CloudFrame` and `ImuFrame` for later perception consumers; no motion,
follow controller, obstacle decision or ROS publisher is present in this phase.

Mounting evidence: user confirms native +Z_lidar points along robot +X_base
(tail → head → forward). This is VERIFIED MOUNTING FACT only. Robot +Y is left,
+Z is up. Full candidate mapping (without additional yaw/roll flips) is
X_base=Z_lidar, Y_base=Y_lidar, Z_base=-X_lidar. Native +X/+Y orientations and
translation remain unverified: do not publish this candidate as a calibrated TF.
The decoder must retain native sensor coordinates. Future base_link → lidar_link
TF owns the mounting transform. Before ROS2/static-TF acceptance, check real
obstacles forward, left and above/ground against base +X, +Y and +Z/-Z and record
the measured sensor-to-base mapping; never tune axes merely by RViz appearance.

Linux C++17 and POSIX only. No Qt or Unitree runtime library. The attribution and
wire layout are in [provenance](L2_DRIVER_PROVENANCE.md); the official reader's
automatic-sync exclusion remains in [audit](L2_SERIAL_SDK_AUDIT.md).

```bash
bash scripts/build_l2_serial_monitor.sh
./build/l2_serial_monitor --device /dev/unitree_l2 --seconds 10 --output reports/l2-10s
./build/l2_serial_monitor --device /dev/unitree_l2 --seconds 60 --output reports/l2-60s
```

Build does not install packages or access hardware. Run only after physical
adapter identity and current UART output are established. Missing persistent
node fails with a discovery instruction, with no ttyACM/ttyUSB fallback. A user
may explicitly select a confirmed device with --device; that is not persistence
or reconnect acceptance. No udev/group/permissions changes are automatic.

Options: `--baudrate 4000000` (only supported value), `--seconds` positive finite
up to 86400, `--output` prefix, `--frames-csv`, `--sample-cloud-frame`,
`--time-scale-num` and `--time-scale-den` (positive finite, default 1/1).
Use a distinct output prefix for each run; outputs at that prefix are replaced.
Raw sec/nsec are available in optional frame CSV; summary timestamps are seconds.
Host elapsed and ratios use first-to-last receive times for each stream, not
total process uptime. Corrected time = first_raw + (raw-first_raw)*num/den.
No raw timestamps are overwritten. A sample CSV contains at most one packet's
points; continuous full point-cloud recording is not implemented.

The summary includes counts, corruption/trailing bytes, decoder errors, cloud
point ranges, finite/nonfinite values, IMU rate/sequence changes and timestamp
statistics. Quaternion is raw, not verified attitude. Unknown packets are counted
without failure; known unsupported types are only classified. `valid_frames`
counts successful framing/CRC even if semantic decoding subsequently fails.

Exit codes: 0 decoded sensor data received; 1 transport/output failure; 2 CLI or
build precondition error; 3 no decoded cloud/IMU (NO_DATA or NO_SENSOR_DATA);
128+signal for interrupted monitoring. A closed descriptor is recorded separately
from data acceptance. No-data alone cannot prove work_mode=0; confirm wiring and
mode independently. If mode prevents UART output, stop: TRANSPORT_SWITCH_REQUIRED.
This tool cannot change that mode, reset, start rotation, sync clocks or configure
network/firmware. No real robot commands are sent.

```bash
python3 -m unittest discover -s tests -p test_l2_serial_core.py -v
```

The transport clears only host input queued before a new run with TCIFLUSH,
after configuring raw 8N1. This prevents pairing old device timestamps with new
host receive times; no output bytes or time command are sent. A PTY regression
test preloads an old valid IMU frame and verifies it is discarded.

On Linux with g++, this compiles both monitor and C++ harness, generates synthetic
fixtures, and tests PTY reception/no output bytes, 8N1/raw/4Mbps settings, timeout,
signal and disconnect. On Windows, the safety source check runs; eight native
tests skip and are covered on Ubuntu CI and Raspberry Pi. Tests never select a
real tty. Latest hardware results are separately recorded in PHASE_B2_REPORT.

Mode activation is a separate, explicit maintenance operation:
`python3 scripts/l2_transport_mode_once.py --host <existing-host-IP> --lidar
<existing-L2-IP> --output <new-report.json>` queries mode only. Add
`--activate-mode-8` only with authorization. Default does not reset; the optional
`--reset-after-verified-set` requires this invocation to SET and read back8.
An already8 device is never rewritten/reset by that activation flow. For Serial
mode verification use `--device /dev/unitree_l2` instead of host/lidar. If a SET
response is uncertain, inspect it through Serial; never blindly repeat activation.
Existing historical mode0/version/sync scripts remain outside this workflow.
