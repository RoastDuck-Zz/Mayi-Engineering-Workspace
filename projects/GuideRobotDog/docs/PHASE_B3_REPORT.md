# Phase B3 — UART / USB transport integrity

Date: 2026-09-09. Base: `40a5b5514912fca053777e2cff26261244cb3b9d`.
Branch: `codex/guidedog-phase-b3-uart-integrity`.

**Serial TRANSPORT_INTEGRITY = FAIL; READY_FOR_ROS2 = NO.**
Read-size changes, another USB port, and later disconnecting Ethernet did not
resolve sustained corruption. The last section separately records the user's
subsequent authorization to switch back to Ethernet. B1/B2/Phase2 reports remain
unchanged. No claim that UART hardware root cause is confirmed.

## USB and kernel evidence

Raspberry Pi 5, aarch64, Ubuntu 24.04.4, kernel 6.8.0-1064-raspi.
Adapter vendor/product 1a86:55d3; USB and tty driver `cdc_acm`.
USB Full Speed: 12 Mbps. Bulk IN endpoint82 maximum64 bytes; bulk OUT02 maximum32;
interrupt IN83 maximum16. `power/control=on`, runtime active, autosuspend delay
2000ms; autosuspend was not enabled or changed. Serial numbers and physical bus
paths remain private. After operator port change, private comparison verified
same adapter serial and different port path; alias recovered and descriptors stayed
identical. L2 was the only USB device moved; F710 was not touched.

TIOCGICOUNT is SUPPORTED on this device. Every capture/monitor had before/after
snapshots. Baseline overrun grew187–201 per10s; all read-size runs grew201–212.
Frame/parity/buf_overrun deltas were0 before port change. First alternate-port run
reported9 frame errors; subsequent runs0. These are driver-reported counters,
not an inferred count from parser errors. rx/tx counters stayed0 despite traffic;
they are not used as measured byte counts.

Linux v6.8 `acm_process_notification` increments overrun from the device's
CDC SERIAL_STATE notification. This supports investigating adapter/UART-side
overflow; it does not identify the exact defective component or prove an
electrical cause. The upstream source is a semantic reference, not proof that
every Ubuntu vendor patch is identical:
[Linux cdc-acm.c](https://github.com/torvalds/linux/blob/v6.8/drivers/usb/class/cdc-acm.c#L270-L328).

Kernel logs were unchanged during all14 monitor runs despite counter growth;
quiet logs do not clear USB. usbmon NOT RUN: debugfs usbmon path absent; no module,
package, driver, power policy, priority or network configuration was changed.

## Exact same-capture replay

Private5s raw SHA256:
`72089a3cfdfd1f1af763c0c4ac568925d0ff3ec6a083060b7cd6d28d4ce030f7`.

Both C++ runtime assembler/decoder/report and independent Python struct/zlib:
480772 bytes,1349 valid frames,109 CRC errors,0 semantic decode errors,
134 cloud,1215 IMU. Cloud and IMU sequence objects agree exactly. Capture tty
overrun delta103, frame/parity/buf_overrun0. Pure capture still contains corruption,
so point geometry processing is not necessary for this failure to occur.

Histogram `declared_length - distance_to_next_complete_valid_header`:

| Difference bytes | Count |
|---:|---:|
| 64 | 46 |
| 128 / 192 / 256 / 512 | 0 each |
| 0 | 107 |
| -80 | 1 |
| -980 | 12 |
| -1044 | 5 |
| -1060 | 2 |
| -1124 | 1 |

The64-byte peak matches bulk-IN packet size, a correlation only. Negative values
mean the next valid frame is farther away, potentially beyond additional damaged
frames. These distances do not prove exact missing byte counts. Only32 candidate
examples are retained in JSON. CRC errors count tail-valid CRC-tested candidates;
tail/length failures are separate. Framing event totals depend on chunking and
must not be compared as exact physical losses between parsers.

## Ten-second software and physical experiments

CRC% = CRC_errors / (valid_frames + CRC_errors) ×100.
Every monitor was4000000 raw8N1, O_RDONLY, TCIFLUSH, timestamp scale1/1.

| Condition | Bytes | Valid | CRC | CRC% | Framing | Cloud | IMU | Overrun delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| read1024 | 974596 | 2706 | 211 | 7.233 | 2012 | 277 | 2429 | 206 |
| read4096 | 970468 | 2698 | 220 | 7.539 | 1999 | 263 | 2435 | 203 |
| read8192 | 979140 | 2691 | 234 | 8.000 | 2030 | 264 | 2427 | 201 |
| read16384 | 982336 | 2711 | 224 | 7.632 | 1988 | 275 | 2436 | 203 |
| read32768 | 994184 | 2709 | 224 | 7.637 | 2025 | 273 | 2436 | 212 |
| baseline1 | 964420 | 2689 | 224 | 7.690 | 1994 | 256 | 2433 | 201 |
| baseline2 | 971772 | 2680 | 251 | 8.564 | 2015 | 252 | 2428 | 187 |
| baseline3 | 970896 | 2718 | 205 | 7.013 | 1918 | 287 | 2431 | 199 |
| alternate1 | 973236 | 2710 | 225 | 7.666 | 1987 | 271 | 2439 | 195 |
| alternate2 | 984280 | 2705 | 224 | 7.648 | 2106 | 268 | 2437 | 201 |
| alternate3 | 980848 | 2699 | 221 | 7.568 | 2031 | 269 | 2430 | 217 |

The operator then discovered both Ethernet and USB had been connected and asked
to isolate that variable. Keeping the alternate USB port, supply and mode8,
Ethernet was removed. Three10s runs remained8.019%,7.608%,8.135% CRC, respectively
234/221/239 CRC errors,2112/2010/2005 framing events,249/251/270 cloud,
2435/2433/2429 IMU; overrun192/199/192, frame/parity/buf_overrun0.
This does not support simultaneous Ethernet attachment as the main cause.

All read-size and initial baseline/alternate runs returned at most128 bytes per
read. Histograms were concentrated in65–511 and1–63; exact64 and512 bins were0.
Increasing requested capacity cannot help when actual reads stay this small.
Across those11 runs maximum processing interval was0.095–0.128ms, process CPU
0.141–0.146s per10s, and maximum sampled1-minute load0.201. /proc process state,
context switches, allowed CPU list and system CPU ticks were retained privately.
No evidence of heavy parser backlog was observed; these samples cannot exclude
all kernel scheduling or bridge/USB latency effects.

Cloud and IMU valid sequences have gaps in every run; duplicates0. Baseline
cloud forward-gap events200/202/221 and estimated missing1800/1771/1775;
IMU forward-gap events57/65/61 and estimated missing59/67/62.
Normal exact1023→0 wraps are separated from other backwards jumps. Estimates
omit ambiguous gaps across wraps; `confirmed_packet_loss=UNKNOWN` throughout.

## Diagnosis and boundaries

Root cause: **LIKELY adapter/UART receive-overflow path; exact cause UNKNOWN**.
Independent same-byte agreement, corruption without geometry decoding, stable
failure across read capacities and ports, and device-reported overrun all reduce
the likelihood of a userspace parser/chunk-size defect. UART wiring/electrical
integrity, adapter firmware/buffering and USB/kernel timing remain candidates.
No software transport fix was justified by the evidence. No CRC relaxation,
repair, padding, baud change, realtime scheduling or hardware replacement was tried.
Serial final60s NOT RUN because neither physical experiment improved integrity;
the user's conditional60s criterion was not met. Next hardware work would change
only one variable: known-good adapter/cable, then UART TX/RX/GND and oscilloscope.

## Software changes and verification

Added bounded capture (default5s, max10s/16MiB), C++ replay, independent Python
replay, sequence statistics, read-size matrix support, read/processing/CPU metrics,
redacted USB diagnostics, tty counters, and a bounded private host-evidence runner.
Raw files and existing replay outputs cannot be overwritten through aliases.
Tests cover partial headers, CRC-valid malformed payloads, aliases, size limits,
sequence wrap/gaps, USB redaction and unsupported counters. Initial failing tests
were observed before fixes. Native packet decoder and geometry are unchanged.

Full working-source checks: Windows Python108 tests (10 Linux-native skips),
Pi Python108 tests (10 existing Git-Bash-specific skips); C++188 assertions PASS,
Node9 tests PASS, shell18 syntax checks PASS. These platform skips are complementary.
Exact-commit fresh-tree and Actions results are provided in the final review package;
software tests do not prove hardware acceptance.
Raw captures, kernel logs, USB serials, management addresses and credentials are
excluded from Git. The exact source-only fresh tree is tested before push.

## Subsequent user-authorized Ethernet transition

After all B3 Serial tests, the user explicitly authorized mode0 and restart.
This is a separate maintenance operation, not part of the zero-device-write B3
monitor experiments. One SET0 was sent through USB. Immediate readback timed out,
so no automatic retry/reset occurred. A separate Serial GET then confirmed0;
another GET0 immediately before reset guarded one RESET. After reboot, Ethernet
GET read back0. No mode setter or reset was repeated. No timestamp sync was sent.

First10s Ethernet passive observation:3189 datagrams,732 cloud packets,2497 IMU,
CRC0, malformed0, tail0, nonfinite IMU0. IMU sequence forward gaps0; cloud has51
forward-gap events and1 other backwards transition. CRC-zero is not complete
sequence/timestamp acceptance.

Final60s Ethernet:19206 datagrams,4483 cloud packets,14974 IMU packets,
CRC0,malformed0,tail0,nonfinite IMU0; passive receiver sent0 commands.
IMU forward gaps0,duplicates0,wraps14,unexpected backwards0. Cloud forward gaps300,
other backwards8,duplicates0,exact wraps4: sequence continuity remains unresolved.
Cloud/IMU raw clock ratios approximately0.499069/0.499068, correction still off.
The user may remove the USB adapter after successful Ethernet verification while
retaining Ethernet and independent L2 supply. CRC validation passed for this
Ethernet sample, but whole-system acceptance and READY_FOR_ROS2 remain NO.

Current target is Ethernet by user request. Timestamp correction stays disabled
(candidate2/1 retained); native sensor coordinates and verified mounting fact
`+Z_lidar -> +X_base` remain unchanged. Full X/Y mounting verification and ROS TF
remain pending. Robot motion, ROS2, obstacle/follow control: NOT RUN.
