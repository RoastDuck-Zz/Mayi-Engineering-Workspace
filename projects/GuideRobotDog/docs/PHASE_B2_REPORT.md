# Phase B2 hardware acceptance

Base: af4ffc640bbf0d04c1295e843c430adcd090f382. B1 and Ethernet history
remain unchanged. Full transport-integrity acceptance is FAIL, not ROS2 ready.

## Configuration boundary

User explicitly authorized GET mode, one SET to 8 if current non-8, necessary L2
reset, private persistent naming, read-only 10/60-second and shutdown tests.
No sync, IP/MAC, firmware, unrelated configuration, robot motion or GPIO.

`scripts/l2_transport_mode_once.py` is separate from native monitor. No reader
library/runParse. Fixed allowlist: type100 cmd6/value0 GET config (extract only
CRC-valid type107 mode); legacy type2002 payload uint32(8) SET; type100 cmd1/value1
RESET. Pinned v2.0.10 setLidarWorkMode disassembly at 0x1d0 encodes 0x7d2/28-byte
frame. resetLidar at 0xea0 encodes 100/1/1. Public protocol supplies fields/CRC;
official example_lidar_serial.cpp uses SET then reset. set_to_serial_mode.cpp
only sets mode, so reset is optional and disabled by default. No arbitrary mode
or generic command CLI. Evidence output uses exclusive creation before sending;
partial/uncertain writes are never retried. Post-SET uncertainty requires a
separate Serial query, not another activation. Queries have no transaction IDs;
delayed replies cannot establish freshness absolutely. Serial post-reset readback
and actual stream provide the independent confirmation.

Independent review checked allowlist and conservative failure behavior. Tests
cover unknown/already8/query-only/set8/readback/reset gating, corrupt mode frames
and duplicate protection after a partial write. Partial result state survives
exceptions; command-attempt hex records are authoritative for uncertain sends.

## Actual activation

- Existing Ethernet route reused without modification. GET returned 0.
- One SET8 sent; subsequent Ethernet GET returned 8. No repeated SET.
- Serial GET initially received no mode response.
- Another Ethernet GET confirmed8, followed by one exact L2 RESET packet.
  Reset-only invocation reused the audited Connection/QUERY/RESET primitives,
  required current==8 and exclusively created its log before transmitting.
- Serial GET through /dev/unitree_l2 after reset returned8.
- No host-to-L2 clock synchronization was sent. No physical power cycle needed.

## Mounting constraint

User confirms native +Z_lidar → +X_base (tail → head → forward). Decoder remains
native; full candidate rotation and translation are unverified. Architecture,
Serial guide and config now record this fact and the required directional tests
before freezing future TF.

## Persistent identity

Operator-confirmed ttyACM0 has a USB-parent serial. Before installation, exact
VID/PID/serial matching over sysfs identified one tty with all attributes on the
same parent. udevadm verify passed. Installed a private 99-unitree-l2.rules,
reloaded and triggered only this tty, then observed /dev/unitree_l2 -> ttyACM0.
Serial and full topology stay private on Pi; udev/.gitignore excludes the real
machine-specific rule from Git. No user-group or permission changes.

## Initial 10 seconds

Runtime 10.002875 s, bytes 1022180, valid frames 2713, cloud280, IMU2433,
CRC errors229, framing errors2150, 77907 finite XYZ points, 0 nonfinite.
Cloud raw delta4.4595179 / host8.9467394 =0.498451745;
IMU raw delta4.99542526 / host9.99965624 =0.499559699. No time backsteps.
Descriptor close succeeded, exit0. Real data received, but integrity acceptance
is not PASS: corruption requires investigation. Missing measurements are not
filled with zeros. Scale remains1/1 and raw timestamps are unchanged.

## Receive backlog regression and independent corruption check

The first 60s run started with an IMU stamp left from the earlier run: first IMU
raw15.37034654 paired with new host15170.785907276, inflating whole-run ratio to
0.779264633 (cloud0.499563494). A new PTY test preloaded an old valid IMU frame
before opening the monitor; it failed against B1. Fixed by host-only TCIFLUSH
after raw8N1 configuration; the same test and all nine native tests then passed.
This is local input discard, not a sensor command or clock correction.

A separate four-second Python/zlib read-only parser independently observed
977 valid IMUs,127 valid clouds,143 bad cloud candidates and16 bad IMU candidates.
Only two bad candidate samples were retained privately, not a point-cloud dump.
One declared1044-byte cloud had its next frame header at980, consistent with a
64-byte stream gap; another had a correct tail but CRC mismatch. This supports
actual received-stream damage, not solely a C++ CRC implementation discrepancy.
It does not identify whether firmware, UART wiring, bridge or host USB driver
caused it. No baud/config/driver experiment or extra device command was performed.

## Final reads with backlog fix

| Metric | 10 seconds | 60 seconds |
|---|---:|---:|
| Runtime seconds | 10.002341407 | 60.002746791 |
| Bytes | 1065964 | 6302712 |
| Valid framed packets | 2736 | 16271 |
| Cloud frames | 303 | 1711 |
| IMU frames | 2433 | 14560 |
| CRC errors | 253 | 1512 |
| Framing error events | 2238 | 13336 |
| Points, all finite XYZ | 84579 | 476721 |
| Nonfinite IMU values | 0 | 0 |
| Cloud ratio | 0.499491421 | 0.499563380 |
| IMU ratio | 0.499466506 | 0.499567746 |
| Timestamp backsteps | 0 | 0 |
| Exit code | 0 | 0 |

10s native XYZ ranges: X[-7.416377279,6.914573468], Y[-5.133095829,10.985079456],
Z[-0.009060972,4.324722082]. 60s: X[-7.774816578,7.736311078],
Y[-5.694753729,11.016914990], Z[-0.009937984,4.342779692]. No mounting rotation.
60s raw cloud227.39408257→257.30432591, host15561.583444338→15621.456214366;
raw IMU227.33229632→257.30429625, host15561.457419762→15621.453286487.
Frame CSV preserves raw sec/nsec and host monotonic values on Pi.
CRC error fraction among CRC-tested candidates is about8.50%, not near zero;
framing events are not a packet-loss estimate. Confirmed physical loss remains
UNKNOWN. Neither successful process exit nor finite surviving points implies
stream integrity PASS. Timestamp correction suggestion2/1 is recorded disabled;
runtime remains1/1. READY_FOR_ROS2 = NO.

## Streaming shutdown

Updated monitor: normal60s closed successfully; SIGINT after4s received109 cloud/
976 IMU and exited130; SIGTERM after4s received120 cloud/967 IMU and exited143.
Both recorded clean_exit=true. Each subsequent invocation reopened the same
device and received real data. No monitor remained before asking for USB replug.
This establishes streaming lifecycle PASS independently of stream integrity FAIL.

## Physical USB reconnect

With all monitors stopped, user physically unplugged/replugged only the L2 USB
adapter into the same port. USB device number changed3→5; /dev/unitree_l2 restored
to the operator-confirmed tty. Reopened monitor for10s:1040167 bytes,2716 valid
frames,284 cloud,2432 IMU,240 CRC and2266 framing events;79566 finite XYZ points,
0 nonfinite. Ratios cloud0.499522415/IMU0.499570999, exit0 and clean close.
Reconnect lifecycle PASS; reconnection did not repair stream corruption.

## Software checks and next boundary

Windows Python96 discovered/8 Linux skips PASS; Node9 PASS; Shell16 PASS.
Pi native suite9 PASS including187 C++ assertions and stale-backlog regression.
Full tracked-tree Pi checks and exact pushed-HEAD CI status are verified before
the final review package. Old B1/Ethernet reports and decoder geometry unchanged.
Git placeholder identity corrected locally only; no old commit was rewritten.

Actual transmitted commands: GET CONFIG for mode readbacks, SET WORK MODE8 once,
L2 RESET once. No other command types. Forbidden writes NONE; robot motion,
GPIO/power-cut, ROS2, follow and obstacle-avoidance implementation NOT RUN.
Local udev changes and input queue discard are host operations, not device packets.

Next: investigate corruption across UART wiring, bridge and host USB reception,
using bounded evidence; do not silently accept dropped frames. Only after clean
stream integrity and an explicitly reviewed timestamp policy should ROS2 work
start. Also verify native X/Y mounting directions before freezing TF.
