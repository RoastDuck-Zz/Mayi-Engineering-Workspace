# B3 execution plan

User-approved investigation, base40a5b55, branch codex/guidedog-phase-b3-uart-integrity.
No L2 commands, reset, time sync, baudrate changes or coordinate transform.

1. Read-only USB sysfs/descriptors and TIOCGICOUNT with explicit unsupported state.
2. Tests first: sequence wrap/gaps; bounded raw capture; C++ replay of exact raw
   input vs independent Python struct/zlib; bad-candidate gap histogram; allowed
   read sizes and actual read histogram/processing time; redaction and tty errors.
3. Implement isolated capture/replay, monitor instrumentation, private raw excludes.
4. Pi software tests; capture once and compare both parsers over identical bytes.
5. Before/after tty counters and kernel logs for each run; five read-size10s runs,
   baseline3x10s, scheduling samples. Do not install packages or alter drivers.
6. If corruption persists, one user-requested USB-port-only change, re-inventory,
   repeat3x10s. Run60s only if improved. Record unsupported usbmon/counters honestly.
7. Evidence-based fix only after regression test; preserve strict CRC. Full Windows,
   Pi, clean tracked tree and CI verification; commit/push and stop for review.
