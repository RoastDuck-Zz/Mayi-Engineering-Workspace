import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_status import format_status  # noqa: E402
from server import ControlService, MockRobotAdapter, RobotDogServer  # noqa: E402


class StatusFormattingTests(unittest.TestCase):
    def test_dogstatus_is_concise(self):
        output = format_status(
            {
                "connected": True,
                "estopped": True,
                "estop_reason": "watchdog",
                "controller_active": False,
                "controller_id": None,
                "motion_state": "趴卧",
                "battery": 80,
                "max_motor_temperature": 39.5,
            }
        )
        self.assertIn("连接: 已连接", output)
        self.assertIn("急停: 急停中", output)
        self.assertIn("原因: watchdog", output)
        self.assertIn("控制权: 空闲", output)
        self.assertNotIn("{", output)


class SoftwareEstopApiTests(unittest.TestCase):
    def setUp(self):
        self.adapter = MockRobotAdapter("10.21.20.1")
        self.service = ControlService(self.adapter, "mock", "10.21.20.1")
        self.server = RobotDogServer(("127.0.0.1", 0), self.service, "test-pin")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.service.stop_event.set()

    def request_json(self, path: str, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method="GET" if body is None else "POST",
            headers={
                "X-Control-Pin": "test-pin",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=2) as response:
            return json.load(response)

    def test_test_estop_endpoint_changes_software_state_only(self):
        engaged = self.request_json("/api/test/estop", {"estopped": True})
        self.assertTrue(engaged["ok"])
        self.assertTrue(engaged["status"]["estopped"])
        self.assertEqual(engaged["status"]["estop_reason"], "test")
        self.assertFalse(self.adapter.connected)

        cleared = self.request_json("/api/test/estop", {"estopped": False})
        self.assertFalse(cleared["status"]["estopped"])
        self.assertEqual(cleared["status"]["estop_reason"], "none")
        self.assertFalse(self.adapter.connected)

    def test_status_api_contains_debug_fields(self):
        payload = self.request_json("/api/status")
        self.assertTrue(payload["ok"])
        for field in (
            "connected",
            "estopped",
            "estop_reason",
            "controller_active",
            "controller_id",
            "last_velocity_at",
            "controller_seen_at",
        ):
            self.assertIn(field, payload["status"])

    def test_emergency_endpoint_never_unlocks_and_keeps_connection(self):
        self.request_json("/api/connect", {"client_id": "owner"})
        for _ in range(2):
            payload = self.request_json("/api/estop", {"client_id": "observer"})
            self.assertTrue(payload["status"]["estopped"])
            self.assertTrue(payload["status"]["connected"])
            self.assertEqual(payload["status"]["estop_reason"], "button")
            self.assertEqual(payload["status"]["motion_state"], "阻尼")


if __name__ == "__main__":
    unittest.main()
