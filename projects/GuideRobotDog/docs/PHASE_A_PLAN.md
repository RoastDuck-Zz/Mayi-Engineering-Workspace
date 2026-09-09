# Phase A execution plan

Scope approved by the user: Architecture Baseline + L2 Serial Migration.
Work stays in this project on `codex/guidedog-phase-a-l2-serial`.

1. Read root instructions, runtime, services, tests, scripts and L2 evidence.
   Record initial Git state; preserve all pre-existing untracked files.
2. Add `tests/test_l2_serial_discover.py` before the discovery script. Run with
   `python -m unittest discover -s tests -p test_l2_serial_discover.py -v`.
   Exercise unsupported hosts, empty and multiple candidate inventories,
   missing tools and failed metadata queries using local fixtures only.
3. Add `scripts/l2_serial_discover.sh`: list USB topology and tty metadata;
   never open a serial device, select a candidate, or alter configuration.
   Run those tests again and check shell syntax.
4. Add `docs/FINAL_ARCHITECTURE.md`; update `config/l2.yaml`, `docs/L2_README.md`
   and `README.md` to separate Serial targets from Ethernet historical evidence.
   Add an entirely commented `udev/99-unitree-l2.rules.example`.
5. Run the full Python and Node suites and syntax-check each shell script.
   Review the complete diff for scope, unsafe commands, secrets, unsupported
   success claims and inconsistent documentation. Preserve the historical
   report byte-for-byte. Record results in `docs/PHASE_A_REPORT.md`.
6. Stage only Phase A files, commit and push the feature branch without force.
   Report the actual SHA and stop for ChatGPT review.

No Pi connection, real SDK execution, mode writes, GPIO, network changes,
robot motion or ROS2 integration. Serial hardware results remain NOT RUN.
The optional native monitor and diagnostics wrapper are deferred; this phase
does not introduce an unverified SDK interface or a second runtime path.
