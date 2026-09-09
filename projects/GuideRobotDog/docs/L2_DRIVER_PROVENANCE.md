# L2 Serial Core v1 provenance

Date: 2026-09-09. The native core is the receive foundation for future lidar
obstacle avoidance and target following. Neither behavior is implemented here.

## Official source used

Unitree unilidar_sdk2 v2.0.10, commit
`0e3c51f512e6b8ff60b8c32f160b412cb48445c2`, BSD-3-Clause.
The downloaded archive hash matches `config/sdk.lock.json`.

- [Protocol header](https://github.com/unitreerobotics/unilidar_sdk2/blob/0e3c51f512e6b8ff60b8c32f160b412cb48445c2/unitree_lidar_sdk/include/unitree_lidar_protocol.h):
  magic, packet IDs, tail, sec/nsec, field order and array bounds.
- [Utilities](https://github.com/unitreerobotics/unilidar_sdk2/blob/0e3c51f512e6b8ff60b8c32f160b412cb48445c2/unitree_lidar_sdk/include/unitree_lidar_utilities.h):
  CRC polynomial/initialization and calibrated cloud geometry. The geometry in
  `native/l2_serial/l2_packet_decoder.cpp` is an attributed adaptation of
  `parseFromPacketToPointCloud`; it reads fields explicitly in little endian,
  bounds point_num, uses double intermediates and preserves the raw timestamp.
  Ring=1 is the upstream per-packet convention, not a measured laser channel ID.
- Official serial example specifies 4000000 baud. It was never executed.
- `native/l2_serial/UNITREE-LICENSE.txt` retains the complete upstream license;
  decoder source retains copyright attribution. Redistributed binaries must
  include that notice. No SDK archive or proprietary reader is linked.

## Wire contract and historical evidence

`scripts/l2_wire_analyzer.py` and `docs/L2_PHASE2_REPORT.md` corroborate payload-only
CRC with historical Ethernet evidence. Header comments incorrectly imply CRC
includes the header. Validate CRC over bytes `[12, size-12)`, stored at `size-12`.
The final two bytes are 00 FF. Header length is the whole frame, little endian.

| Packet | Total | Payload fields used (offset relative to payload) |
|---|---:|---|
| IMU 104 | 80 | seq 0, sec 8, nsec 12, quaternion 16, gyro 32, acceleration 44 |
| Cloud 102 | 1044 | calibration 52, scan fields 84, count 116, ranges 120, intensities 720 |

Actual field sizes supersede stale upstream comments (IMU 156, cloud 1036).
Cloud ranges use the packet's scale/bias and range limits, as in official
conversion. Zero ranges are omitted. Each cloud packet is one `CloudFrame`, not
an aggregated revolution. No extrinsics, IMU pose correction or person identity
inference is applied. 2D/control/parameter packets are classified/countable;
only 3D and IMU payloads are decoded in v1. DataInfo.payload_size semantics across
firmware remain unverified; outer fixed length controls all bounds.

## Independently written project code

- `serial_transport.*`: Linux O_RDONLY, termios B4000000, raw 8N1, poll/read/close.
  No transmit API, SDK calls, modem-control ioctl or software flow-control output.
- `frame_assembler.*`: bounded stream buffering, resynchronization, length/tail/
  CRC validation, unknown packet preservation. Max declared length 65536 bytes.
  A plausible incomplete unknown frame waits for its bounded declared length;
  trailing bytes are reported at shutdown. No guessing nested frames in payload.
- `l2_packet_decoder.*`: explicit endian-safe field extraction and value objects;
  geometry adaptation specifically identified above.
- `timestamp_analyzer.*`: paired device/host observations, raw delta and ratio;
  optional host-only correction anchored at first raw timestamp. Default 1/1,
  never auto-detects or forces 2/1. Backsteps invalidate the ratio.
- `diagnostic_report.*`, `l2_serial_monitor.cpp`: bounded statistics, strict CLI,
  optional metadata CSV and one sample cloud, finite JSON or null, signal/error
  exit propagation. Counts of observed events may be zero; absent measurements
  are null. DATA_RECEIVED means decoded data, not sensor acceptance PASS.
- Tests: synthetic Python struct/zlib fixtures; independently known XYZ case;
  C++ core harness and Python pseudoterminal integration. No PCAP, private USB
  identity, management address or credentials are committed.

## Concept-only external reference

[markgol/l2lidar_node](https://github.com/markgol/l2lidar_node) is GPL-3.0.
Only its public README architecture, timestamp correction/synchronization
distinction and ROS point/IMU interface concepts were consulted. No L2lidar.cpp,
L2lidar.h, class, function or renamed implementation was copied. The project's
own historical measurement supplies the approximately half-speed observation;
we do not infer Serial behavior from it. Qt and ROS code are not dependencies.
This is independent transport/framing implementation from protocol evidence,
not a claim of a formal multi-person clean-room legal process.

## Physical limitations

No explicit DTR/RTS commands are sent; CRTSCTS and HUPCL are disabled. Kernel USB
driver behavior on opening/configuring a real adapter remains hardware-specific.
O_RDONLY and the no-transmit API prevent protocol command bytes; they do not
establish electrical line behavior without measurement. Tests with PTYs prove
software behavior, not actual baud stability or sensor timebase.
