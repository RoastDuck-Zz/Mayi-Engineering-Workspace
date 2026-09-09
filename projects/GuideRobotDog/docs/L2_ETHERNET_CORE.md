# L2 Ethernet Core

The current L2 transport is a passive UDP receiver. Defaults are bind
`192.168.1.2:6201` and source `192.168.1.62:6101`; every value is overrideable
for an isolated test link. The receiver never sends packets and has no mode,
reset, time-sync, firmware, or network configuration API.

`l2_udp_monitor` requests a 4 MiB receive buffer and records the actual kernel
value. It enables `SO_RXQ_OVFL` and reads the ancillary counter from `recvmsg`;
missing ancillary data is reported as null. It also records `/proc/net/snmp`
UDP fields and `/sys/class/net/<interface>/statistics` through the read-only
host helper. No sysctl is changed.

UDP datagrams are validated independently. A datagram may contain several
complete protocol frames, so the validator advances inside that datagram only;
it never combines two datagrams. Each frame requires magic, bounded declared
length, exact available bytes, `00 ff` tail and payload CRC. Bad frames are
dropped before decoder use. Unknown CRC-valid types are counted.

Sequence numbers use modulo 1024. Delta 0 is a duplicate, delta 1 is normal,
delta 2–512 is an immediate forward gap, and delta above 512 is a possible late
or reordered packet. A 64-sequence window retains missing candidates; a later
arrival marks a reorder and removes that candidate, while candidates that age
out become unrecovered. `confirmed_packet_loss` remains UNKNOWN.

Every Cloud/IMU gap records previous/current sequence, modulo delta, raw device
timestamp delta and host monotonic delta. Nominal periods use only CRC-valid,
decode-valid sequence-consecutive frames and report count, min, median/p50,
p95 and max for raw and host intervals. Timestamp correction is anchored:
`raw_first + (raw - raw_first) * 2/1`; it remains diagnostics-only until the
Ethernet continuity gate is accepted. Raw timestamps are always retained.

Private capture records are GDL2UDP1: 8-byte magic, then arrival monotonic ns,
source port/IP, payload length and raw datagram. Capture and replay enforce a
new 0600 output, 10-second/16 MiB bounds, and no overwrite aliases. Raw files
and host logs are ignored by Git.
