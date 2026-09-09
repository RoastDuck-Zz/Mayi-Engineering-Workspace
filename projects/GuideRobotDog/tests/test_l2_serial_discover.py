"""Exercise metadata discovery with synthetic filesystem/command fixtures only."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")
GIT_BASH = Path(GIT).resolve().parents[1] / "bin/bash.exe" if GIT else Path("missing")
BASH = str(GIT_BASH) if GIT_BASH.is_file() else shutil.which("bash")


@unittest.skipUnless(BASH, "Bash is unavailable")
class SerialDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.dev = self.root / "dev"
        self.sys = self.root / "sys/class/tty"
        for directory in (self.bin, self.dev, self.sys):
            directory.mkdir(parents=True)
        self.write_command("uname", "echo Linux\n")
        self.write_command("lsusb", 'case "$*" in "") echo fixture-usb;; -t) echo fixture-topology;; *) exit 90;; esac\n')
        self.write_command("udevadm", 'case "$*" in "info --query=property --name="*|"info --attribute-walk --name="*) echo fixture-metadata;; *) exit 90;; esac\n')

    def write_command(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body, encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def run_discovery(self, isolated_path=False):
        env = os.environ.copy()
        env.update(
            L2_TEST_PATH=(
                ("/" + self.bin.drive[0].lower() + self.bin.as_posix()[2:]
                 if os.name == "nt" else self.bin.as_posix())
                + ("" if isolated_path else ":/usr/bin:/bin")
            ),
            L2_DISCOVERY_DEV_ROOT=self.dev.as_posix(),
            L2_DISCOVERY_SYS_TTY_ROOT=self.sys.as_posix(),
        )
        return subprocess.run(
            # Git Bash prepends system paths at startup; set fixture PATH after
            # startup so uname/USB commands cannot fall through to the host.
            [BASH, "-c", 'export PATH="$L2_TEST_PATH"; exec /bin/bash "$1"',
             "fixture", str(ROOT / "scripts/l2_serial_discover.sh")],
            env=env, cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )

    def test_unsupported_host_refuses_before_usb_inspection(self):
        self.write_command("uname", "echo MINGW64_NT\n")
        result = self.run_discovery()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Linux", result.stdout)
        self.assertNotIn("fixture-usb", result.stdout)

    def test_empty_inventory_does_not_claim_lidar_enumeration(self):
        result = self.run_discovery()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("candidate_count=0", result.stdout)
        self.assertIn("L2 identity: UNKNOWN", result.stdout)
        self.assertIn("READY FOR ROS2: NO", result.stdout)
        self.assertIn("fixture-topology", result.stdout)

    def test_multiple_candidates_are_all_reported_without_opening_them(self):
        for name in ("ttyACM0", "ttyUSB1"):
            (self.dev / name).write_text("DO NOT OPEN", encoding="utf-8")
            (self.sys / name / "device").mkdir(parents=True)
        result = self.run_discovery()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("candidate_count=2", result.stdout)
        for name in ("ttyACM0", "ttyUSB1"):
            self.assertIn(name, result.stdout)
            self.assertEqual((self.dev / name).read_text(), "DO NOT OPEN")
        self.assertNotIn("DO NOT OPEN", result.stdout)
        self.assertIn("L2 identity: UNKNOWN", result.stdout)
        self.assertIn("fixture-metadata", result.stdout)
        self.assertIn("OVERRIDDEN", result.stdout)

    def test_missing_tools_report_incomplete_instead_of_success(self):
        (self.bin / "lsusb").unlink()
        result = self.run_discovery(isolated_path=True)
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertIn("UNAVAILABLE: lsusb", result.stdout)
        self.assertIn("READY FOR ROS2: NO", result.stdout)

    def test_metadata_failure_preserves_failure_and_continues_inventory(self):
        (self.dev / "ttyACM0").touch()
        (self.sys / "ttyACM0/device").mkdir(parents=True)
        self.write_command("udevadm", "exit 7\n")
        result = self.run_discovery()
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertIn("exit_status=7", result.stdout)
        self.assertIn("candidate_count=1", result.stdout)
        self.assertIn("Serial SDK runtime: NOT RUN", result.stdout)
