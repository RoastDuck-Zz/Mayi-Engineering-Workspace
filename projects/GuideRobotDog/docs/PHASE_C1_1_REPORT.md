# Phase C1.1 — Official SDK A/B, packet-loss state, timestamp policy, mount amendment

## Scope

This phase remains Ethernet-only and does not enter ROS2, Point-LIO, Nav2,
obstacle avoidance, follow control, or robot-network work. The official SDK is
used only through its normal Ethernet receive path for comparison. No explicit
mode, reset, timestamp-sync, IP, MAC, firmware, or motor command was issued.

## Official SDK provenance

- Repository: `unitreerobotics/unilidar_sdk2`
- Tag: `v2.0.10`
- Commit: `0e3c51f512e6b8ff60b8c32f160b412cb48445c2`
- `cloud_scan_num=1`, `use_system_timestamp=false`
- Raw packets were read with `getLidarPointDataPacket()` and
  `getLidarImuDataPacket()`, not only aggregated clouds.
- ARM64 build and initialization passed. `runParse()` returned data normally.
- `closeUDP()` still segfaults on ARM64 after the summary flush; this is recorded
  as `SDK_CLEANUP=FAIL` and was isolated in a child process. It is not treated as
  fixed by process isolation.

## Sequential A/B evidence

The passive and official receivers were run sequentially on the same L2, cable,
Pi address, and mode 0 endpoint. Passive A1: 690 Cloud / 2,494 IMU, 49 Cloud
gap events, 1,453 estimated missing positions, CRC/tail/length/source errors 0.
Official B1/B2/B3: 672/683/688 Cloud raw packets and 2,497/2,496/2,496 IMU
packets; estimated Cloud missing positions 1,357/1,346/1,420; no duplicates;
`runParse_negative=0`. Official Cloud raw-rate estimates remained in the same
order as the passive receiver. This supports `OFFICIAL_AND_PASSIVE_MATCH` for
the Cloud-gap behavior; it does not prove the physical root cause.

Official 60-second run: 4,097 Cloud raw packets, 14,960 IMU raw packets,
8,494 estimated Cloud missing positions, Cloud missing fraction 0.6746, IMU
missing fraction 0, Cloud raw ratio 0.48665, IMU raw ratio 0.49863. The SDK
reported no packet-lost state changes: `packet_lost_up_changed=0` and
`packet_lost_down_changed=0` in the observed samples.

## Passive decoder additions

The pinned protocol layout is used for `LidarInsideState`: `packet_lost_up` at
payload offset 28 and `packet_lost_down` at offset 32 after `DataInfo`. Values
are reported as raw fields and changed counts; they are not described as a
percentage or rate. Gap observations include before/after values and a strict
timestamp-span consistency result. Consistency is `UNKNOWN` until at least 30
valid delta-1 nominal samples exist, then uses a 0.80–1.20 ratio window.

## Timestamp policy

The clean-room policy follows the behavior of markgol/l2lidar_node at commit
`e9931d5d9e9239829737b18c2485d23f155bc7cb` without copying GPL code. Host sync
and oscillator correction are separate. The correction is anchored elapsed
scaling:

`corrected = raw_anchor + (raw - raw_anchor) * 2 / 1`

The epoch is never multiplied directly. The official raw rates confirm the
approximately 0.5 device clock scale; the 2/1 policy is recorded but no ROS2
timestamp publisher is created in this phase.

## Mounting amendment

The current verified fact is `+Z_lidar -> -Z_base` because the L2 is now
confirmed inverted. The former `+Z_lidar -> +X_base` statement in C1-era
reports is historical and superseded; those original reports are not rewritten.
Native X/Y, full rotation, and translation remain unknown. No TF is published.

## Result

- Official SDK data path: `PASS` for build, initialize, receive, and raw packet
  comparison; cleanup `FAIL` due to the known ARM64 `closeUDP()` crash.
- Cloud continuity: `FAIL` for autonomous safety; official and passive gaps
  match in scale.
- Timestamp policy: `PASS` for anchored 2/1 implementation and raw-rate evidence.
- ROS2: `NOT STARTED` by phase gate.
- Ready for ROS2 review: `NO`, pending the cleanup decision, Cloud continuity
  disposition, and physical X/Y mounting verification.
