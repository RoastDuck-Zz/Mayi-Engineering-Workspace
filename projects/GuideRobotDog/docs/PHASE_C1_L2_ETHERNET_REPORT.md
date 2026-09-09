# Phase C1 — L2 Ethernet driver foundation

Branch: `codex/guidedog-l2-ethernet-ros2`.

This phase implements a passive native Ethernet transport, bounded capture and
offline replay, independent Python validation, modulo-1024 sequence diagnostics,
64-packet reorder-window accounting, timestamp gap evidence, SO_RCVBUF and
SO_RXQ_OVFL reporting, and read-only host UDP/NIC counter snapshots. It does
not write L2 configuration, move the robot, touch robot networking, or install
ROS2.

The Pi already had mode0 and the independent Ethernet link. Three 10-second
runs had CRC/tail/malformed/wrong-source zero, SO_RXQ_OVFL no delivered counter,
UDP InErrors/RcvbufErrors zero and NIC rx errors/drops zero. IMU sequence had no
gaps. Cloud had 47–51 immediate jumps per 10 seconds.

The 60-second run received 18,958 datagrams, 4,182 Cloud frames and 14,968 IMU
frames. CRC, tail, malformed and size errors were zero. SO_RXQ_OVFL was enabled
but delivered no ancillary counter; UDP and NIC drops/errors remained zero.
Cloud had 291 immediate gaps and 8,701 estimated missing sequence positions.
The first gap sample 11→46 had raw timestamp delta 0.08115 s and host delta
0.16264 s; nominal raw Cloud period median was 0.00231942 s. IMU had zero gaps,
15 wraps, and nominal raw median 0.002 s. The Cloud jumps therefore track a
longer device-time interval and are not explained by a host socket counter.

Classification: `LINK_OR_SOURCE_LOSS_LIKELY`; exact source/hardware cause remains
unproven. `ETHERNET_TRANSPORT_INTEGRITY=FAIL` for the full driver gate because
Cloud continuity is not yet acceptable. This phase does not enter ROS2; Jazzy is
not installed on the Pi. Raw and private host evidence remain outside Git.

## Socket and replay evidence

The monitor requested `SO_RCVBUF=4194304`; Pi `getsockopt` returned `425984`,
while read-only `/proc/sys/net/core/rmem_max` was `212992`. The requested value
was therefore constrained by the existing kernel limit; no sysctl was modified.
`SO_RXQ_OVFL` was supported but no ancillary counter was delivered, so its delta
is null rather than fabricated zero.

A five-second private capture contained 1,579 datagrams and 487,486 bytes. C++
replay and independent Python `struct`/`zlib` analysis agreed exactly:
1,579 datagrams, 344 Cloud, 1,249 IMU, CRC/tail/malformed/size errors all zero.
Capture SHA256 is
`366d735ce3796b8f63993b8985bab82d33a8f5e2f413f3e3900c56b72b8369`.

No ROS2 driver was created in C1. The Pi lacks ROS2 Jazzy and the Cloud gap
classification fails the full transport gate. `l2_mount_probe.py` is an
observation-only helper for future manual axis evidence; it never writes TF.
