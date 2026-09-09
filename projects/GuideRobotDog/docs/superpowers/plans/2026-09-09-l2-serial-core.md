# L2 Serial Core v1 implementation plan

User-approved scope: direct independent Serial Core implementation, superseding
the pending SDK-alternative decision in the earlier B1 plan. Preserve both local
reproducibility/CI commits and all pre-existing untracked files.

Architecture: Linux read-only termios/poll transport → bounded byte-stream
assembler → little-endian packet decoder → host timestamp/statistics → monitor.
No SDK library, Qt, ROS, command transmitter or automatic device selection.
Default /dev/unitree_l2, 4000000 baud, 8N1, scale 1/1. Missing observations are null.

1. Protocol/fixtures: derive 80-byte IMU and 1044-byte cloud offsets from pinned
   Unitree BSD definitions. Confirm CRC(payload only) against historical analyzer.
   Construct synthetic fixtures with Python struct/zlib, no real identifiers.
2. Tests first: C++ harness covers split header/frame, concatenation, garbage,
   corrupt CRC/tail/length recovery, malformed payload, cloud/IMU values, unknown,
   empty stream and timestamp scale/ratio/backsteps. Run missing-core failure.
3. Implement native/l2_serial frame_assembler, l2_packet_decoder and
   timestamp_analyzer with explicit bounds and no struct reinterpretation.
4. Test transport/monitor via Linux pseudoterminal: actual bytes in, no bytes out,
   8N1/raw flags, no fallback, finite CLI validation, signal/timeout/disconnect,
   JSON nulls and optional one-frame CSV. Then implement serial_transport,
   diagnostic report and l2_serial_monitor; build script compiles only our source.
5. Run parser and PTY tests on Ubuntu WSL; add Ubuntu CI invocation, preserve
   Windows existing tests. No actual tty or official SDK is used in tests.
6. Record BSD notices/provenance and concept-only markgol README references.
   Update README, L2_README, config and B1 report to native-core software evidence.
7. Full Python/Node/shell/C++ and exported tracked-tree verification; independent
   code review; fix demonstrated issues; explicit staging, small commits and
   normal push on current B1 branch. Stop for ChatGPT review.

Hardware gate: no confirmed accessible Pi target. ARM64 build, USB enumeration,
10/60-second receive and physical cleanup remain NOT RUN unless obtained safely.
No permanent configuration, time writes, robot motion or GPIO actions.
