# Phase A.1 + B1 implementation plan

Goal: Repository Reproducibility + L2 Serial Safe Bring-up.
Approved scope is the user's Phase B1 request; base is
`32fc870ed45f04f87669303f48351b0963c9ca24`, branch
`codex/guidedog-phase-b1-serial-bringup`.

Architecture: preserve the robot runtime; add an independently invoked Serial
probe using only audited pinned SDK APIs. Separate source evidence, software
fixtures and target results. No implicit start/mode/reset/sync command, tty
fallback, package install, network/GPIO operation, ROS2 or autonomous feature.

## Task 1 — Fresh-clone reproducibility

- Reproduce the existing untracked deployment-document dependency in a clean
  archive of the base commit, without moving or deleting the user's files.
- Preserve the local historical deployment guide (it contains private management
  addresses and an obsolete Windows path). Create public `docs/PI_DEPLOYMENT.md`.
- Change the contract test to consume the new public guide, observe failure before
  adding the guide, and update README. Verify the complete tracked tree later.

## Task 2 — GitHub CI

- Add root `.github/workflows/guidedog-ci.yml`, push/PR path-filtered to this
  project and itself, with read-only permissions and Windows software checks.
- Audit Bash/platform fixture assumptions; add Ubuntu when reliable. Test native
  statistics/probe behavior using a fake SDK, never a hardware library in CI.
- Run Python unittest, Node tests and individual shell syntax checks. No hardware
  SDK installation, device connection, service start, network or GPIO mutation.

## Task 3 — Pinned Unitree Serial SDK audit

- Fetch only the official archive identified by config/sdk.lock.json, verify its
  SHA256 and inspect headers, Serial example, visible source and CMake.
- Record exact initializeSerial signature, baudrate, parsing/cloud/IMU APIs,
  rotation and configuration commands, initialization and teardown uncertainty
  in docs/L2_SERIAL_SDK_AUDIT.md before implementing the probe.
- Distinguish CONFIRMED FROM SOURCE, CONFIRMED FROM TARGET TEST and UNKNOWN.

## Task 4 — Safe Serial runtime probe

- First add software tests for the CLI and statistics using fixture SDK data:
  missing samples yield null; invalid samples cannot look successful; timestamp
  deltas/ratios use matched monotonic intervals; invalid arguments precede SDK use.
- Implement native/l2_serial_probe.cpp only after audit. Require explicit device,
  bounded duration and a new output location. Preserve raw timestamps and ranges.
- No work-mode/reset/sync/IP setters or default rotation command. If temporary
  start semantics remain uncertain, omit start support entirely.
- Save pre-cleanup evidence before closeSerial/destruction, then completion only
  after those return. Never mask a crash with _Exit or a fake cleanup PASS.

## Task 5 — Serial tooling/tests

- Test build/run wrappers before implementation using command/filesystem fixtures.
  Missing SDK is NOT READY; missing device directs to discovery; no first-tty
  fallback; errors and runtime exit codes propagate without mutation.
- Add build_l2_serial_probe.sh and run_l2_serial_probe.sh. Build only the probe,
  never official examples. Keep the existing discovery and udev template.
- Bound runtime externally so vendor hangs cannot be reported as clean exits.

## Task 6 — Target Pi evidence if safely available

- Check for an already configured, authorized SSH route without scanning hosts or
  exposing credentials. Read-only inventory/compilation only if safely available.
- If no usable route, mark all checks NOT RUN ON TARGET and continue software work.
- Mode mismatch: TRANSPORT SWITCH REQUIRED; stop hardware testing. Never switch it.

## Task 7 — Documentation/report

- Update README, L2 README and config with implemented tooling and actual evidence.
- Add PHASE_B1_REPORT.md with source audit, tests, fresh-tree result, CI status,
  safety findings and unknowns. Keep historical reports unchanged.
- Inspect changed content for secrets, management addresses, MAC/USB serials and
  raw data. Exclude all pre-existing untracked files and generated outputs.

## Task 8 — Full verification + commit + push

- Run `python -m unittest discover -s tests -v`, `node --test tests/test_*.cjs`
  and `for script in scripts/*.sh; do bash -n "$script" || exit 1; done`.
- Export a clean tracked tree (git archive of commits), run the full software
  verification there and record exact pass/fail/skip counts.
- Review diff/status and request independent read-only code review. Make small
  scoped commits, push without force, inspect CI if available, then stop.
- Finish with the requested CHATGPT REVIEW PACKAGE; no further implementation.
