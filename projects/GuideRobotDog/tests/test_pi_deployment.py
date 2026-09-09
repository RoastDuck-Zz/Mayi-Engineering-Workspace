import configparser
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def load_unit(relative_path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read_string(read(relative_path))
    return parser


class RaspberryPiDeploymentTests(unittest.TestCase):
    def test_web_service_is_mock_safe_and_exposes_only_port_8088(self):
        service = load_unit("robotdog-web.service")["Service"]
        command = shlex.split(service["ExecStart"])

        self.assertEqual(service["User"], "guidedog")
        self.assertEqual(service["WorkingDirectory"], "/home/guidedog/robotdog-control")
        self.assertIn("/home/guidedog/robotdog-control/scripts/run-server.sh", command)
        self.assertEqual(command[command.index("--mode") + 1], "mock")
        self.assertEqual(command[command.index("--port") + 1], "8088")
        self.assertEqual(command[command.index("--robot-ip") + 1], "10.21.20.1")
        self.assertEqual(service["EnvironmentFile"], "-/etc/robotdog-web.env")
        self.assertEqual(load_unit("robotdog-web.service")["Unit"]["Description"], "Mymooo Robot Controller")

    def test_run_server_requires_project_virtualenv(self):
        script = read("scripts/run-server.sh")
        self.assertIn('PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"', script)
        self.assertIn("Python virtual environment not found", script)
        self.assertNotIn('PYTHON_BIN="/usr/bin/python3"', script)

    def test_run_server_process_rejects_missing_virtualenv(self):
        git = shutil.which("git")
        bash = Path(git).resolve().parents[1] / "bin" / "bash.exe" if git else None
        if bash is None or not bash.is_file():
            self.skipTest("Git Bash is unavailable on this test host")
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            scripts = project / "scripts"
            scripts.mkdir()
            shutil.copy2(ROOT / "scripts" / "run-server.sh", scripts / "run-server.sh")
            result = subprocess.run(
                [str(bash), "scripts/run-server.sh"], cwd=project,
                capture_output=True, text=True, timeout=5, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python virtual environment not found", result.stderr)

    def test_python_requirements_are_empty(self):
        for filename in ("requirements-base.txt", "requirements-hardware.txt"):
            packages = [
                line.strip() for line in read(filename).splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            self.assertEqual(packages, [])

    def test_bpx_installer_uses_venv_and_optional_pinned_ref(self):
        script = read("scripts/install-bpx-sdk.sh")
        self.assertIn("BPX_SDK_REF", script)
        self.assertIn("UNPINNED SDK VERSION", script)
        self.assertIn('"${PROJECT_DIR}/.venv/bin/python" -m pip install', script)
        self.assertNotIn("--user", script)
        self.assertIn('git -C "${SDK_DIR}" fetch --prune origin', script)

    def test_setup_and_deploy_are_explicit_and_mock_only(self):
        setup = read("scripts/setup-pi.sh")
        deploy = read("scripts/deploy-pi.sh")
        for package in ("python3", "python3-venv", "python3-pip"):
            self.assertIn(package, setup)
        self.assertIn('python3 -m venv "${PROJECT_DIR}/.venv"', setup)
        self.assertIn("requirements-base.txt", setup)
        self.assertNotIn("requirements-hardware.txt", setup)
        self.assertIn('DEPLOY_DIR="/home/guidedog/robotdog-control"', deploy)
        self.assertIn("robotdog-web.service", deploy)
        self.assertNotIn("--mode bpx", deploy)

    def test_retained_network_scripts_are_operator_only(self):
        mdns = read("scripts/configure-mdns-hostname.sh")
        self.assertIn('MDNS_HOSTNAME="${1:-mymooo}"', mdns)
        self.assertIn('WIFI_INTERFACE="${2:-wlan0}"', mdns)
        wired = read("scripts/configure-wired-network.sh")
        self.assertIn("10.21.20.1", wired)
        self.assertIn("nmcli", wired)
        self.assertNotIn("server.py", wired)

    def test_pin_example_is_separate_from_python_source(self):
        self.assertEqual(read("etc/robotdog-web.env.example"), "MYMOOO_PIN=000000\n")
        self.assertNotIn("123456", read("server.py"))


if __name__ == "__main__":
    unittest.main()
