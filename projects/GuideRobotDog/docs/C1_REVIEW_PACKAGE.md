# C1 review package — Unitree L2 Ethernet

## Scope

This phase covers only passive Unitree L2 Ethernet reception and diagnostics. It does not change the L2 device, the robot network, motion control, ROS2 runtime, TF publication, navigation, obstacle avoidance, or follow behavior.

The receiver uses a native C++ UDP parser for the observed L2 wire frames. It validates datagram boundaries, frame length, tail marker, and CRC before passing sensor-native bytes to the existing decoder. No official Unitree SDK, `runParse`, setter, reset, firmware command, or outbound packet is used.

## Live acceptance evidence

- L2 Ethernet mode was already explicitly authorized and verified as `work_mode=0`.
- Endpoint: L2 `192.168.1.62:6101` to Pi host `192.168.1.2:6201`.
- Three 10-second passive runs: 3,148 / 3,168 / 3,181 datagrams; all CRC, tail, malformed-frame, size, wrong-source, UDP, and NIC error counters were zero.
- 60-second passive run: 18,958 datagrams, 5,563,448 bytes, 4,182 Cloud frames, and 14,968 IMU frames. CRC, tail, malformed-frame, size, wrong-source, UDP, and NIC error counters were zero.
- Cloud sequence gaps persisted while IMU remained contiguous. Classification is `LINK_OR_SOURCE_LOSS_LIKELY`; Ethernet frame integrity is not accepted as loss-free.
- A bounded 5-second capture was replayed through both C++ and Python analyzers. Frame counts, CRC/tail/length checks, and stream counts agreed; capture SHA-256 is recorded in `PHASE_C1_L2_ETHERNET_REPORT.md`.

## Gates and limitations

- `SO_RCVBUF` requested 4 MiB, actual 425,984 bytes; Pi `rmem_max` is 212,992. `SO_RXQ_OVFL` is supported but no ancillary drop counter was delivered during the runs.
- ROS2 Jazzy is absent on the Pi, so no ROS2 package or live topic/TF acceptance was started.
- Mounting evidence is partial: native `+Z_lidar -> +X_base` is verified. Native X/Y and the complete rotation remain unverified; no static TF was published.

## Software verification

- Windows: Python `113` tests passed, `10` skipped; Node transport tests `9` passed.
- Raspberry Pi: C++ serial/core assertions `192` passed; UDP core tests `5` passed; Ethernet tools built with `-Wall -Wextra -Werror`.
- GitHub Actions builds the passive Ethernet tools on Ubuntu and runs the existing Windows/Ubuntu software suites.

The detailed evidence and command outputs are in [PHASE_C1_L2_ETHERNET_REPORT.md](PHASE_C1_L2_ETHERNET_REPORT.md).
