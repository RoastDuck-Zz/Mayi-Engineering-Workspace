# Pinned Unitree L2 Serial SDK audit

Date: 2026-09-09. **Runtime safety blocker found before probe implementation.**
The pinned x86_64 library's receive path implicitly synchronizes device time.
Setting `use_system_timestamp=false` does not disable this operation. No target
SDK or real tty was opened during this audit.

## Provenance

Source of truth: [sdk.lock.json](../config/sdk.lock.json).

- Official repository: https://github.com/unitreerobotics/unilidar_sdk2
- Tag: v2.0.10; commit: `0e3c51f512e6b8ff60b8c32f160b412cb48445c2`.
- Downloaded official tag archive SHA256 matches the lock:
  `8313a85e4bc1a47b73f98cccb9c887c41d897d6a71e800e9b5b03cd4f0fc8131`.
- Archive extracted into ignored local vendor storage, not committed or installed.
- Visible native SDK files comprise public headers, examples, CMake and prebuilt
  aarch64/x86_64 archives. The reader and serial implementation .cpp files are
  not provided in this native SDK tree. Binary inspection below is explicitly
  distinct from source review and hardware execution.

## CONFIRMED FROM SOURCE

The [public reader header](https://github.com/unitreerobotics/unilidar_sdk2/blob/0e3c51f512e6b8ff60b8c32f160b412cb48445c2/unitree_lidar_sdk/include/unitree_lidar_sdk.h)
declares the following exact signature:

```cpp
virtual int initializeSerial(
    std::string port = "/dev/ttyACM0",
    uint32_t baudrate = 4000000,
    uint16_t cloud_scan_num = 18,
    bool use_system_timestamp = true,
    float range_min = 0,
    float range_max = 100
) = 0;
```

The documented return is 0 for successful serial open and -1 for failure.
This is not evidence of correct transport mode, valid sensor data or safe shutdown.
The 4,000,000 baud value is also explicitly used by the Serial example.
The SDK's default tty name is not acceptable as an automatic deployment fallback.

| API/type | Source contract |
|---|---|
| `createUnitreeLidarReader()` | Returns `UnitreeLidarReader*` |
| `runParse()` | Main receive/parse entry; 0 no valid message, 102 point data, 104 IMU |
| `getPointCloud(PointCloudUnitree&) const` | bool; cloud has double `stamp`, id, ringNum, vector of points |
| `getImuData(LidarImuData&) const` | bool; IMU contains raw sec/nsec, quaternion, angular velocity, linear acceleration |
| `getLidarPointDataPacket() const` | const reference to raw parsed point packet |
| `closeSerial()` / `closeUDP()` | Separate virtual bool methods |
| Reader destruction | No virtual destructor or public reader-free function is declared |

Deleting a derived reader through this non-virtual-destructor base pointer is
not a supported safe ownership solution. A future probe must document this
upstream lifetime limitation, not copy a UDP _Exit wrapper and claim it fixed.

[Utilities](https://github.com/unitreerobotics/unilidar_sdk2/blob/0e3c51f512e6b8ff60b8c32f160b412cb48445c2/unitree_lidar_sdk/include/unitree_lidar_utilities.h)
define x/y/z/intensity/time/ring. The point conversion chooses the packet's
sec+nsec timestamp when `use_system_timestamp=false`; this only defines timestamp
selection in the visible conversion code, not absence of device clock writes.
[Protocol declarations](https://github.com/unitreerobotics/unilidar_sdk2/blob/0e3c51f512e6b8ff60b8c32f160b412cb48445c2/unitree_lidar_sdk/include/unitree_lidar_protocol.h)
give USER_CMD_STANDBY_TYPE values 0=start, 1=standby. They do not prove a start
command is required for reading a device already configured for power-on auto start.

The [Serial example](https://github.com/unitreerobotics/unilidar_sdk2/blob/0e3c51f512e6b8ff60b8c32f160b412cb48445c2/unitree_lidar_sdk/examples/example_lidar_serial.cpp)
explicitly calls `startLidarRotation()`, `setLidarWorkMode(8)` and `resetLidar()`.
Its shared `example.h` additionally stops and starts rotation and uses unbounded
loops. **Official example unsafe for passive diagnostics: YES.** It was not run.
Start is not established as a mandatory read prerequisite; no start option is
approved by this audit. No mode-switch utility is introduced.

[CMake](https://github.com/unitreerobotics/unilidar_sdk2/blob/0e3c51f512e6b8ff60b8c32f160b412cb48445c2/unitree_lidar_sdk/CMakeLists.txt)
sets C++17, includes `include`, links `lib/${CMAKE_SYSTEM_PROCESSOR}/libunilidar_sdk2.a`
and builds examples plus configuration utilities; it does not build reader source.
Future project builds should compile only the selected project tool, never run
those upstream examples/configuration utilities. SDK config header reports 2.0.9,
consistent with the previously recorded tag/runtime version difference.

## CONFIRMED FROM STATIC BINARY INSPECTION — not target tests

Used existing Ubuntu WSL `nm -C`, `objdump -drC` and `objdump -rC` on the exact
archive's x86_64 static library. No SDK code was executed. Local disassembly and
relocations remain in ignored reports; the reproducible findings are:

1. Reader constructor, address `0x15a0`: initializes internal byte at `0x2598`
   to false; `0x15e0` zeros the timestamp storage starting at `0x25a0`.
2. `initializeSerial` forwards the public timestamp boolean to `initializeBasic`;
   the latter stores it at a **different offset, `0x97c`**, instruction `0x18ae`.
3. `runParse`, `0x2855`, checks `0x2598`; after an elapsed-time comparison it calls
   `*0x98(vptr)` at `0x289c` and sets the flag true at `0x28a8`. This gate does not
   test the timestamp-selection byte at `0x97c`.
4. Relocation table for `_ZTVN13unilidar_sdk221UnitreeLidarReaderImpE` maps entry
   `0xa8` directly to `UnitreeLidarReaderImp::syncLidarTimeStamp()`.
   Constructor uses table+`0x10` as the address point, so offset `0x98` resolves
   to that entry. This also agrees with zero-based virtual slot 19 in the header.
5. The sync routine's Serial path calls `Serial::flush` and `Serial::write` for
   a 32-byte command; it is a device write, not merely a host timestamp read.
6. `runParse` also references version, parameter and time-delay requests. It is
   not a byte-passive parser even when the caller invokes no explicit setters.
7. `initializeSerial` visibly opens/configures the serial transport, flushes input,
   sets timeout and calls `initializeBasic`. It must not be described as metadata-only.
8. `closeSerial` at `0xb40` calls `Serial::close` and deletes the Serial transport
   object. `closeUDP` at `0xbb0` calls `UDPHandler::Close` and deletes a different
   transport object. They are separate branches, not proof of identical cleanup.

An independent read-only review confirmed the implicit-sync interpretation.
These addresses describe this x86_64 archive only. The aarch64 archive has not
been independently disassembled or run in this phase; do not claim this as Pi
execution evidence or as an exhaustive proof of every internal side effect.

## CONFIRMED FROM TARGET TEST

None for the official SDK path in Phase B1. A later independently implemented
native monitor was compiled and tested on Pi; see PHASE_B1_REPORT.md for its
10-second no-sensor-data result. Current work mode remains UNKNOWN; last
historical Ethernet readback was 0. No transport switch, reset or sync was sent.

## UNKNOWN / runtime gate

- No public API in the pinned header disables automatic timestamp synchronization.
  `use_system_timestamp=false` is insufficient. There is no established compliant
  receive path through the public pinned API under the user's no-auto-sync rule.
- Full ARM64 initialization/parser/cleanup behaviour and USB driver line-control
  effects remain unverified. No claim of Serial cleanup success is justified.
- VID/PID, USB serial/topology, actual tty, permissions, current transport mode,
  timestamp rate and reconnect stability remain UNKNOWN.
- No memory-offset patch, vtable patch, silent command interception, SDK replacement
  or fake acquisition loop is an approved workaround.

The official receiving path remains blocked and is not the project's Serial
runtime. The user subsequently authorized an independent native core using
official BSD protocol/geometry evidence, without linking the reader library.
See L2_DRIVER_PROVENANCE.md and L2_SERIAL_CORE.md. This resolves the software
dependency on the automatic-sync path; it does not establish hardware acceptance.
A successful Serial open must not automatically mark mode=8 verified.
