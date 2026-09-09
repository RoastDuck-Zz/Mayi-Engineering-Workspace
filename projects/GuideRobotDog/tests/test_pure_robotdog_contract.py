import inspect
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from server import RobotDogServer  # noqa: E402


class PureRobotDogContractTests(unittest.TestCase):
    def parse_with(self, argv, environment):
        with patch.dict(os.environ, environment, clear=True), patch.object(
            sys, "argv", ["server.py", *argv]
        ):
            return server.parse_args()

    def test_cli_contains_only_robotdog_options(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "server.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        options = set(re.findall(r"--[a-z][a-z-]*", result.stdout))
        self.assertEqual(options, {"--help", "--host", "--port", "--robot-ip", "--mode", "--pin"})

    def test_server_constructor_has_no_external_subsystems(self):
        parameters = list(inspect.signature(RobotDogServer.__init__).parameters)
        self.assertEqual(parameters, ["self", "address", "service", "pin"])

    def test_project_owned_real_robot_adapter_is_named_mymooo(self):
        self.assertTrue(hasattr(server, "MymoooRobotAdapter"))
        self.assertFalse(hasattr(server, "BpxRobotAdapter"))

    def test_explicit_pin_overrides_both_environment_names(self):
        args = self.parse_with(
            ["--pin", "cli-pin"],
            {"MYMOOO_PIN": "new-pin", "ROBOTDOG_PIN": "legacy-pin"},
        )
        self.assertEqual(args.pin, "cli-pin")

    def test_mymooo_pin_precedes_legacy_environment_name(self):
        args = self.parse_with(
            [], {"MYMOOO_PIN": "new-pin", "ROBOTDOG_PIN": "legacy-pin"}
        )
        self.assertEqual(args.pin, "new-pin")

    def test_legacy_pin_remains_supported(self):
        self.assertEqual(
            self.parse_with([], {"ROBOTDOG_PIN": "legacy-pin"}).pin,
            "legacy-pin",
        )

    def test_missing_pin_environment_leaves_runtime_random_fallback(self):
        self.assertIsNone(self.parse_with([], {}).pin)

    def test_user_facing_surfaces_use_mymooo_brand(self):
        user_files = (
            "server.py",
            "web/index.html",
            "web/app.js",
            "README.md",
            "docs/PI_DEPLOYMENT.md",
            "robotdog-web.service",
            "requirements-hardware.txt",
        )
        content = "\n".join((ROOT / name).read_text(encoding="utf-8") for name in user_files)
        self.assertIn("Mymooo", content)
        self.assertNotRegex(content, r"(?i)Black[ -]?Panther|黑豹")

    def test_official_sdk_and_compatibility_identifiers_are_retained(self):
        source = (ROOT / "server.py").read_text(encoding="utf-8")
        installer = (ROOT / "scripts/install-bpx-sdk.sh").read_text(encoding="utf-8")
        for identifier in (
            "bpx_sdk",
            "MotionLevelControl",
            "DEFAULT_CLIENT_ROBOT_STATE_UDP_PORT",
        ):
            self.assertIn(identifier, source)
        for identifier in ("bpx_sdk_open", "BPX_SDK_REF"):
            self.assertIn(identifier, installer)
        self.assertIn('choices=("mock", "bpx")', source)

    def test_external_subsystem_files_are_absent(self):
        forbidden = (
            "nexarm_stage2",
            "k230",
            "tools",
            "modules/camera_manager.py",
            "modules/camera_process.py",
            "modules/network_manager.py",
            "modules/nexarm_adapter.py",
            "modules/nexarm_kinematics.py",
            "robotdog-wifi-fallback.service",
            "scripts/wifi-fallback-hotspot.sh",
            "scripts/ik_endpoint_check.py",
            "deploy",
        )
        self.assertEqual([path for path in forbidden if (ROOT / path).exists()], [])

    def test_runtime_sources_contain_no_external_subsystem_terms(self):
        runtime_files = (
            ROOT / "server.py",
            ROOT / "web/index.html",
            ROOT / "web/app.js",
            ROOT / "web/styles.css",
            ROOT / "robotdog-web.service",
        )
        forbidden = (
            "nexarm",
            "gemini",
            "orbbec",
            "k230",
            "mjpeg",
            "video-port",
            "camera",
            "wifi-interface",
            "/api/network/",
        )
        combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in runtime_files)
        self.assertEqual([term for term in forbidden if term in combined], [])

    def test_service_starts_only_mock_robotdog_on_8088(self):
        unit = (ROOT / "robotdog-web.service").read_text(encoding="utf-8")
        exec_start = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
        self.assertIn("--mode mock", exec_start)
        self.assertIn("--port 8088", exec_start)
        for term in ("video", "nexarm", "gemini", "camera", "wifi-interface", "8089"):
            self.assertNotIn(term, exec_start.lower())

    def test_bpx_wired_network_script_remains_isolated(self):
        script = (ROOT / "scripts/configure-wired-network.sh").read_text(encoding="utf-8")
        compact = " ".join(script.split())
        self.assertIn('INTERFACE="eth0"', script)
        self.assertIn("10.21.20.2/24", script)
        self.assertIn("ipv4.gateway \"\"", compact)
        self.assertIn("ipv4.dns \"\"", compact)
        self.assertIn("ipv4.never-default yes", compact)

    def test_no_non_bpx_hardware_requirements_remain(self):
        lines = [
            line.strip()
            for line in (ROOT / "requirements-hardware.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(lines, [])

    def test_pin_example_is_present_but_not_hardcoded_in_python(self):
        example = (ROOT / "etc/robotdog-web.env.example").read_text(encoding="utf-8")
        server = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertEqual(example.strip(), "MYMOOO_PIN=000000")
        self.assertNotIn('ROBOTDOG_PIN = "123456"', server)
        self.assertNotIn('MYMOOO_PIN = "123456"', server)


if __name__ == "__main__":
    unittest.main()
