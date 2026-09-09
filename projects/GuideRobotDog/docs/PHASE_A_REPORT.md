# Phase A review record

Date: 2026-09-09. Repository: RoastDuck-Zz/Mayi-Engineering-Workspace.
Project: projects/GuideRobotDog. Branch: codex/guidedog-phase-a-l2-serial.
This report records local software verification, not target hardware acceptance.

## Initial inspection

Read the root AGENTS.md, README, L2 README and Phase 2 report, F710 guide,
L2 configuration, server.py, gamepad.py, gamepad service, existing tests and scripts.
The root instructions contain no additional development rules.

Requested Git checks were run before edits:

```text
git status: main, up to date with origin/main; no tracked edits; untracked files below
git branch --show-current: main
git remote -v: origin https://github.com/roastduck-zz/Mayi-Engineering-Workspace.git (fetch/push)
git log -10 --oneline:
7c6c53d feat(robotdog): integrate GuideRobotDog workspace
9c440ae chore: reinitialize engineering workspace
```

Only two commits existed. Base SHA: `7c6c53dab204449c6573af97423331583736bed3`.
Created the requested feature branch without replacing files. The following
pre-existing untracked files were preserved and excluded from the Phase A commit:

- MYMOOO_WIFI_MANAGEMENT_REPORT.md
- PURE_ROBOTDOG_CLEANUP_REPORT.md
- RASPBERRY_PI5_DEPLOY.md
- docs/L2_DEVELOPMENT_REPORT.md
- docs/history/2026-09-07-pure-robotdog-cleanup-plan.md
- docs/history/2026-09-07-raspberry-pi5-stage1-plan.md
- docs/history/MIGRATION_STAGE1_REPORT.md
- docs/history/RASPBERRY_PI5_MIGRATION_AUDIT.md
- docs/history/README.md
- docs/superpowers/plans/2026-09-07-mymooo-wifi-management.md
- docs/superpowers/specs/2026-09-07-mymooo-wifi-management-design.md

## Deliverables

- FINAL_ARCHITECTURE.md defines hardware topology, orthogonal OperatingMode and
  SafetyState, soft/hard E-stop, arbitration/supervision and future data flow.
- config/l2.yaml separates Serial targets and NOT RUN acceptance from historical
  Ethernet evidence. The file remains a record, not an applied runtime configuration.
- L2_README.md is Serial-first and keeps explicit references to the unmodified
  historical Phase 2 report. README summarizes current status and future boundaries.
- l2_serial_discover.sh collects USB/tty metadata only. It does not open a tty,
  select a device, write configuration, install tools or change the network.
- Five fixture-based tests exercise unsupported hosts, empty/multiple candidates,
  missing tools and failed metadata queries. Fixtures are not sensor evidence.
- The udev example is entirely commented: TEMPLATE ONLY / NOT READY TO INSTALL.
- The optional native Serial monitor and additional diagnostics wrapper were not
  added. Serial API signatures and library side effects must be reviewed before
  implementing that runtime; no guessed SDK call was introduced.

## Verification

Host: Windows, Python 3.11.15, Node v24.17.0, Git Bash 5.3.9. No existing project
venv was available; used the available Python interpreter, without package installs.

| Check | Result |
|---|---|
| Initial Python baseline | PASS, 71 tests |
| Final Python unittest discovery | PASS, 76 tests, no skips |
| Node test runner | PASS, 9 tests, no skips |
| Shell syntax | PASS, all 15 scripts individually checked with Git Bash |
| New discovery regression tests | PASS, 5 tests; first run failed before implementation |
| Independent static review | No substantive findings |
| Historical report and runtime diff | Empty for L2_PHASE2_REPORT.md, server.py, gamepad.py and gamepad service |

Commands used:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
python -m unittest discover -s tests -v
node --test tests/test_*.cjs
# Invoke Git Bash -n separately for every scripts/*.sh file.
```

Equivalent Bash syntax sweep:

```bash
for script in scripts/*.sh; do bash -n "$script" || exit; done
```

One intermediate Python run failed after setting only PYTHONIOENCODING: an
existing CLI subprocess test decoded UTF-8 output as GBK. Setting PYTHONUTF8 as
well resolved the mismatch; the final full run passed without changing old tests.
The new fixture initially encountered Git Bash's prepended system PATH, then
explicitly set the fixture PATH after shell startup so OS/USB calls stay simulated.

Reproducibility limitation: an existing test reads the pre-existing untracked
RASPBERRY_PI5_DEPLOY.md, and README already references that local document.
The 76-test PASS describes this workspace, not a fresh clone. This unrelated
document was neither published nor removed to make the new commit appear clean.
Fresh-clone full-suite verification: NOT RUN.

## Hardware acceptance

| Hardware check | Result |
|---|---|
| L2 serial enumeration on Pi | NOT RUN |
| Official SDK serial runtime | NOT RUN ON TARGET |
| Point cloud | NOT RUN |
| IMU | NOT RUN |
| Timestamp 10-second window | NOT RUN |
| Stability at least 60 seconds | NOT RUN |
| Serial clean shutdown | NOT RUN |
| USB reconnect | NOT RUN |
| Robot motion | NOT RUN |
| Hard power cut | NOT RUN |
| READY FOR ROS2 | NO |

## Safety, unknowns and scope review

No Pi connection, real bpx_sdk operation, L2 mode write, timestamp sync, firmware
operation, network change, GPIO operation or power cut was performed.
No runtime Mode Manager, Arbiter, SafetyState, remote hard E-stop UI, ROS2,
Point-LIO, Nav2, Follow, Patrol or camera code was implemented.

Actual tty identity, VID/PID, USB serial/topology, device permissions, current
work mode, effective serial settings, Serial clock behaviour, cleanup/reconnect,
mount extrinsics and the hard power-cut design remain UNKNOWN.
The current legacy action-estop toggle differs from the future explicit RESET/ARM
contract; FINAL_ARCHITECTURE.md records this for later implementation review.

The changed documents distinguish target design from implementation and hardware
evidence. The historical Phase 2 report is unchanged; existing Ethernet tools
are retained. New source has no GPIO/SDK/network mutation path or dead runtime
scaffolding. No secrets, real USB identifiers, private management addresses,
PCAP, raw logs, point clouds, build output, venv or temporary reports are intended
for this commit; historical L2 bench endpoints remain explicitly labelled.

## Proposed Phase B — not implemented

After ChatGPT review, collect Pi serial metadata, identify the real adapter and
review the pinned official Serial API before bounded SDK runtime tests.
If the mode is wrong, stop and seek separate explicit authorization for a
one-time transport change. Revalidate point cloud, IMU, timestamps, clean
shutdown and USB reconnect before considering ROS2. Full mode/safety control
implementation requires its own reviewed scope.

After the Phase A feature commit is pushed, stop for ChatGPT review.
