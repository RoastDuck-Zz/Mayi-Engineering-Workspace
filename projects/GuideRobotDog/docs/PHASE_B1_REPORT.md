# Phase B1 / L2 Serial Core v1

Date: 2026-09-09. Branch: `codex/guidedog-phase-b1-serial-bringup`.
Base: `32fc870ed45f04f87669303f48351b0963c9ca24`.

Goal: receive data for future lidar obstacle avoidance and lidar target following.
Implemented transport, framing, cloud/IMU decoding, timestamp analysis and monitor;
neither obstacle decisions nor tracking/motion control are claimed complete.

## Implementation and audit

- Preserved reproducibility commit `b35f4b3` and CI commit `173c99d`.
  Public deployment contract no longer depends on the untracked private guide.
- Official pinned reader excluded: its runParse implicitly synchronizes time.
  [Audit](L2_SERIAL_SDK_AUDIT.md) retains source/binary/target distinctions.
- Independent Linux C++17 O_RDONLY termios/poll transport, 4000000 baud/raw/8N1.
  No SDK, Qt, command writer, mode change, reset, time sync or tty fallback.
- Bounded stream buffer, header/length/tail/payload-CRC checks, corruption recovery.
  Cloud 1044 bytes, IMU 80 bytes; stale official comments corrected from fields.
- Explicit endian decoding and attributed BSD cloud geometry. Raw IMU values,
  finite checks, host/device timing and optional anchored 1/1-default scaling.
- JSON counters and null measurements; optional metadata CSV and one cloud sample.
  No raw point stream recorded. [Usage](L2_SERIAL_CORE.md), [provenance](L2_DRIVER_PROVENANCE.md).
- Windows/Ubuntu CI requires Linux compiler and runs native tests through unittest.
  Independent static review found and fixed test output isolation: a missing-device
  test now uses its temporary directory instead of overwriting a default report.

## Software verification

- Windows full Python: 84 discovered, 77 executed, 7 Linux native tests skipped.
- Node: 9 PASS.
- Shell: 16 scripts syntax checked.
- Raspberry Pi: Ubuntu 24.04.4, aarch64, g++ 13.3.0, native ELF ARM64 built.
- Native tests on Pi: 8 PASS including 187 C++ assertions. Covers every IMU split,
  concatenation, garbage, bad length/CRC/tail recovery, decoded XYZ/IMU, invalid
  nsec/count, nonfinite input, timestamps, unknown and empty input. PTY tests verify
  zero output bytes, raw 8N1/B4000000, no-data, signal and disconnect propagation.
- Initial x86_64 tests passed before user requested direct Pi testing; subsequent
  Linux testing uses the Pi. No further WSL use.
- Fresh tracked tree and final GitHub Actions status are recorded in the final
  review package after the committed tree is verified and pushed.

## Actual hardware evidence

User supplied the Pi SSH destination and explicitly identified the only serial
adapter as L2 (the other USB device is F710). Authorized this session's explicit
`--device /dev/ttyACM0` read-only run under sudo. No group or udev changes.
Management address, credentials, USB serial and raw topology are not committed.

| Check | Evidence |
|---|---|
| USB serial enumeration | PASS, one candidate correlated by operator |
| /dev/unitree_l2 | ABSENT; no fallback was performed |
| Current tty | /dev/ttyACM0, explicitly authorized this session |
| Current work mode | UNKNOWN; historical Ethernet readback 0 |
| 10-second native receive | 10.002618 s, 1 byte, 0 valid frames, exit code 3 |
| Point cloud / IMU | NOT OBSERVED |
| Timestamp ratio | UNAVAILABLE; first/last/delta/ratio remain null |
| 60-second receive | NOT RUN: stopped after absent sensor data |
| Close | Descriptor close succeeded; streaming shutdown remains NOT RUN |
| USB reconnect | NOT RUN |
| Device command writes | NONE |
| work_mode modified | NO |
| Robot motion / power cut | NOT RUN / NOT RUN |

**TRANSPORT_SWITCH_REQUIRED investigation:** historical mode 0 may prevent UART
data, but one byte/no frames does not prove mode or exclude wiring/adapter issues.
Stopped hardware reception; did not send configuration queries or changes.
Raw discovery and frame metadata remain private on the Pi, separate from Git.
No official SDK code was executed and no service/network/GPIO changes were made.

## Remaining work

Resolve UART-output prerequisites with separately authorized mode/wiring checks;
then repeat 10/60-second reads, establish timestamps, streaming shutdown and
reconnect stability. Only after trustworthy input is available should obstacle
extraction and target tracking consume CloudFrame/ImuFrame and integrate with
the robot's safety control. This iteration stops for review after push.
