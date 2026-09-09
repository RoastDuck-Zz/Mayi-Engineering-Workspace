import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASH = Path(shutil.which("git") or "").resolve().parents[1] / "bin" / "bash.exe"


class ManagementScriptFixture:
    def __init__(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.sys_net = self.root / "sys" / "class" / "net"
        self.log = self.root / "mutations.log"
        self.bin.mkdir()
        self.sys_net.mkdir(parents=True)
        (self.sys_net / "wlan0").mkdir()
        (self.sys_net / "eth0").mkdir()
        self.log.write_text("", encoding="utf-8")
        self._write_fakes()

    def close(self):
        self.temporary.cleanup()

    def _write(self, name, content):
        path = self.bin / name
        path.write_text("#!/usr/bin/env bash\n" + content, encoding="utf-8", newline="\n")

    def _write_fakes(self):
        self._write(
            "ip",
            r'''
if [[ "$*" == "link show dev wlan0" ]]; then
  [[ "${FAKE_WLAN_STATE:-UP}" == "UP" ]] && echo '2: wlan0: <BROADCAST,UP,LOWER_UP>' || echo '2: wlan0: <BROADCAST>'
elif [[ "$*" == "-4 -o addr show dev wlan0 scope global" ]]; then
  [[ "${FAKE_WLAN_IPV4:-yes}" == "yes" ]] && echo '2: wlan0 inet 192.168.8.116/24 brd 192.168.8.255 scope global dynamic wlan0'
elif [[ "$*" == "route show default" ]]; then
  [[ "${FAKE_DEFAULT_WLAN:-yes}" == "yes" ]] && echo 'default via 192.168.8.1 dev wlan0' || echo 'default via 192.168.10.1 dev eth0'
elif [[ "$*" == "-4 -o addr show dev eth0 scope global" ]]; then
  echo '3: eth0 inet 192.168.10.3/24 brd 192.168.10.255 scope global eth0'
elif [[ "$*" == "-br link show dev wlan0" ]]; then
  echo "wlan0 ${FAKE_WLAN_STATE:-UP}"
elif [[ "$*" == "-br -4 addr show dev wlan0" ]]; then
  [[ "${FAKE_WLAN_IPV4:-yes}" == "yes" ]] && echo 'wlan0 UP 192.168.8.116/24'
elif [[ "$*" == "-br link show dev eth0" ]]; then
  echo 'eth0 UP'
elif [[ "$*" == "-br -4 addr show dev eth0" ]]; then
  echo 'eth0 UP 192.168.10.3/24'
elif [[ "$*" == "-br addr show eth0" ]]; then
  echo 'eth0 UP 10.21.20.2/24'
elif [[ "$*" == "route get 10.21.20.1" ]]; then
  echo '10.21.20.1 dev eth0 src 10.21.20.2'
fi
''',
        )
        self._write(
            "systemctl",
            r'''
if [[ "$1" == "is-active" ]]; then
  if [[ "$2" == "--quiet" ]]; then
    [[ "${FAKE_SSH_ACTIVE:-yes}" == "yes" ]]
  else
    [[ "${FAKE_SSH_ACTIVE:-yes}" == "yes" ]] && echo active || { echo inactive; exit 3; }
  fi
fi
''',
        )
        self._write(
            "nmcli",
            r'''
if [[ "$*" == "-t -f NAME connection show" ]]; then exit 0; fi
echo "nmcli $*" >> "${FAKE_MUTATION_LOG}"
''',
        )
        self._write("sudo", 'echo "sudo $*" >> "${FAKE_MUTATION_LOG}"\n')
        self._write("hostname", "echo guidedog\n")
        self._write("uname", "echo aarch64\n")
        self._write(
            "ss",
            "echo 'LISTEN 0 5 0.0.0.0:8088 0.0.0.0:*'\n",
        )

    def run(self, script, *arguments, **overrides):
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": f"{self.bin.as_posix()}:/usr/bin:/bin",
                "MYMOOO_SYS_CLASS_NET": self.sys_net.as_posix(),
                "FAKE_MUTATION_LOG": self.log.as_posix(),
                "FAKE_WLAN_STATE": "UP",
                "FAKE_WLAN_IPV4": "yes",
                "FAKE_DEFAULT_WLAN": "yes",
                "FAKE_SSH_ACTIVE": "yes",
            }
        )
        environment.update(overrides)
        return subprocess.run(
            [str(BASH), str(ROOT / "scripts" / script), *arguments],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )

    def mutations(self):
        return self.log.read_text(encoding="utf-8")


@unittest.skipUnless(BASH.is_file(), "Git Bash is unavailable")
class WiredNetworkGuardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ManagementScriptFixture()

    def tearDown(self):
        self.fixture.close()

    def assert_refused_without_mutation(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Wi-Fi management channel is not ready", result.stderr)
        self.assertIn("Refusing to reconfigure eth0", result.stderr)
        self.assertEqual(self.fixture.mutations(), "")

    def test_missing_wlan0_is_refused_before_network_mutation(self):
        (self.fixture.sys_net / "wlan0").rmdir()
        self.assert_refused_without_mutation(
            self.fixture.run("configure-wired-network.sh")
        )

    def test_down_wlan0_is_refused_before_network_mutation(self):
        self.assert_refused_without_mutation(
            self.fixture.run("configure-wired-network.sh", FAKE_WLAN_STATE="DOWN")
        )

    def test_wlan0_without_global_ipv4_is_refused_before_network_mutation(self):
        self.assert_refused_without_mutation(
            self.fixture.run("configure-wired-network.sh", FAKE_WLAN_IPV4="no")
        )

    def test_default_route_outside_wlan0_is_refused_before_network_mutation(self):
        self.assert_refused_without_mutation(
            self.fixture.run("configure-wired-network.sh", FAKE_DEFAULT_WLAN="no")
        )

    def test_inactive_ssh_is_refused_before_network_mutation(self):
        self.assert_refused_without_mutation(
            self.fixture.run("configure-wired-network.sh", FAKE_SSH_ACTIVE="no")
        )

    def test_current_ssh_session_on_eth0_is_refused_by_default(self):
        result = self.fixture.run(
            "configure-wired-network.sh",
            SSH_CONNECTION="192.168.10.2 50000 192.168.10.3 22",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Current SSH session appears to be using eth0", result.stderr)
        self.assertIn("ssh guidedog@<wlan0-ip>", result.stderr)
        self.assertEqual(self.fixture.mutations(), "")

    def test_force_bypasses_only_eth0_session_guard_after_preflight(self):
        result = self.fixture.run(
            "configure-wired-network.sh",
            "--force",
            SSH_CONNECTION="192.168.10.2 50000 192.168.10.3 22",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("sudo nmcli connection", self.fixture.mutations())

    def test_force_cannot_bypass_missing_wifi_ipv4(self):
        self.assert_refused_without_mutation(
            self.fixture.run(
                "configure-wired-network.sh",
                "--force",
                FAKE_WLAN_IPV4="no",
                SSH_CONNECTION="192.168.10.2 50000 192.168.10.3 22",
            )
        )


@unittest.skipUnless(BASH.is_file(), "Git Bash is unavailable")
class ManagementCheckerTests(unittest.TestCase):
    def test_checker_reports_management_state_without_mutating_commands(self):
        fixture = ManagementScriptFixture()
        try:
            result = fixture.run("check-management-link.sh")
            self.assertEqual(result.returncode, 0, result.stderr)
            for expected in (
                "=== Mymooo Management Link Check ===",
                "Hostname:",
                "Architecture:",
                "Wi-Fi:",
                "192.168.8.116/24",
                "Default route:",
                "default via 192.168.8.1 dev wlan0",
                "SSH:",
                "active",
                "Web:",
                "8088 listening",
                "Ethernet:",
                "192.168.10.3/24",
                "IMPORTANT:",
                "Do not reconfigure eth0 until Wi-Fi SSH is verified.",
            ):
                self.assertIn(expected, result.stdout)
            self.assertEqual(fixture.mutations(), "")
            source = (ROOT / "scripts" / "check-management-link.sh").read_text(
                encoding="utf-8"
            )
            for forbidden in (
                "sudo ",
                "nmcli ",
                "hostnamectl ",
                "systemctl start",
                "systemctl stop",
                "systemctl restart",
                "systemctl enable",
            ):
                self.assertNotIn(forbidden, source)
        finally:
            fixture.close()


if __name__ == "__main__":
    unittest.main()
