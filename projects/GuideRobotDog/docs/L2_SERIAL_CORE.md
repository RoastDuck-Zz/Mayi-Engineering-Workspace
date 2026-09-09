# L2 Serial Core v1

Receive foundation for lidar obstacle avoidance and lidar target following.
Exports `CloudFrame` and `ImuFrame` for later perception consumers; no motion,
follow controller, obstacle decision or ROS publisher is present in this phase.

Mounting evidence: the current user-confirmed inverted installation is native
+Z_lidar → -Z_base; the former +Z_lidar → +X_base statement is superseded.
(tail → head → forward). This is VERIFIED MOUNTING FACT only. Robot +Y is left,
+Z is up. Full candidate mapping (without additional yaw/roll flips) is
Native +X/+Y orientations and the complete rotation remain unknown. Native
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
`--time-scale-num` and `--time-scale-den` (positive finite, default 1/1),
`--read-size` (1024, 4096, 8192 default, 16384 or 32768 only).
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
tests plus two B3 native tests skip and are covered on Ubuntu CI and Raspberry Pi.
Tests never select a real tty. Latest transport investigation is PHASE_B3_REPORT;
PHASE_B2_REPORT remains historical evidence.

Mode activation is a separate, explicit maintenance operation:
`python3 scripts/l2_transport_mode_once.py --host <existing-host-IP> --lidar
<existing-L2-IP> --output <new-report.json>` queries mode only. Add
`--activate-mode-8` only with authorization. Default does not reset; the optional
`--reset-after-verified-set` requires this invocation to SET and read back8.
An already8 device is never rewritten/reset by that activation flow. For Serial
mode verification use `--device /dev/unitree_l2` instead of host/lidar. If a SET
response is uncertain, inspect it through Serial; never blindly repeat activation.
Existing historical mode0/version/sync scripts remain outside this workflow.
After B3, the user authorized an Ethernet transition. The same maintenance tool
now also accepts `--activate-mode-0`, mutually exclusive with `--activate-mode-8`.
Default remains query-only. Reset requires this invocation to SET and read back
the selected target; already-target and uncertain readback never reset. A delayed
verification after an uncertain SET requires separate evidence and an explicitly
authorized reset; never repeat the SET merely because an immediate query failed.

## B3 integrity tools

All live B3 tools receive through O_RDONLY at 4000000 raw 8N1; no L2 command,
mode change, reset or timestamp sync is part of this workflow.

```bash
bash scripts/l2_usb_diagnostics.sh
python3 scripts/l2_tty_stats.py --device /dev/unitree_l2
bash scripts/build_l2_serial_integrity.sh
./build/l2_serial_capture --device /dev/unitree_l2 --seconds 5 --output /tmp/new-l2-raw.bin
./build/l2_serial_replay --input /tmp/new-l2-raw.bin --output /tmp/new-l2-cpp.json
python3 scripts/l2_raw_stream_check.py /tmp/new-l2-raw.bin --output /tmp/new-l2-python.json
python3 scripts/l2_integrity_run.py --executable ./build/l2_serial_monitor --prefix /tmp/new-l2-run --seconds 10 --read-size 8192
```

Use existing authorized device access; tools do not change permissions or install
anything. USB identity/topology is redacted unless explicitly using `--private`.
The runner requires a new private directory and records before/after TIOCGICOUNT,
kernel logs and bounded /proc scheduling/load samples. Unsupported counters are
null, not zero; negative/reset deltas are null. CDC driver rx/tx counters may not
measure actual byte traffic, so monitor bytes remain authoritative.

Capture defaults to 5 seconds, permits at most 10 seconds and 16 MiB, creates a
0600 file exclusively, and stops at the byte cap. Raw bytes and host logs remain
private. Both replay outputs require new files, including symlink/hardlink aliases.
Replay accepts at most 16 MiB and never opens a tty. C++ uses the runtime assembler
and decoder; Python independently uses struct/zlib. Host timing and ratios in C++
replay are null because capture bytes do not contain host receive timestamps.

Compare bytes, valid_frames, crc_errors, decode_errors, cloud_frames, imu_frames
and both sequence objects. Valid frames mean length/tail/CRC accepted; cloud/IMU
counts and sequences exclude invalid timestamp nanoseconds or cloud point count.
Framing event counts are parser/chunk dependent, not a physical packet-loss count.
Python bad-candidate examples are capped at 32; its gap histogram measures declared
length minus distance to the next complete CRC-valid frame, not a proven byte loss.

Sequence 1023→0 is an ordinary wrap. Other backwards changes stay unexpected;
missing estimates count forward gaps only and do not invent missing wrap cycles.
`confirmed_packet_loss` remains UNKNOWN. CRC-invalid data is always dropped.

Monitor reports read-return histogram, zero reads/polls, maximum read, process CPU
seconds, total parser processing wall time and `max_processing_gap_ms` (maximum
read-return-to-processing-end wall time, including CSV work if enabled). It does
not isolate kernel wait from scheduler delay. Combine with /proc samples; low
processing time alone cannot exclude all host scheduling or USB-driver failures.
