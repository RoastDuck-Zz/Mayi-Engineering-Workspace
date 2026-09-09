import json
import sys
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import ControlService, MockRobotAdapter, RobotDogServer  # noqa: E402


class MockHttpStage1AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.adapter = MockRobotAdapter("10.21.20.1")
        self.service = ControlService(self.adapter, "mock", "10.21.20.1")
        self.service.MOTION_COMMAND_TTL_SECONDS = 0.08
        self.service.CONTROLLER_TIMEOUT_SECONDS = 0.4
        self.server = RobotDogServer(
            ("127.0.0.1", 0),
            self.service,
            "stage1-pin",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.service.stop_event.set()
        self.adapter.disconnect()

    def request(self, path, body=None, pin="stage1-pin"):
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if pin is not None:
            headers["X-Control-Pin"] = pin
        request = Request(
            self.base_url + path,
            data=data,
            method="GET" if body is None else "POST",
            headers=headers,
        )
        with urlopen(request, timeout=2) as response:
            content_type = response.headers.get_content_type()
            payload = response.read()
            if content_type == "application/json":
                return response.status, json.loads(payload)
            return response.status, payload.decode("utf-8")

    def wait_for_reason(self, reason, timeout=0.5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            _, payload = self.request("/api/status")
            if payload["status"]["estop_reason"] == reason:
                return payload["status"]
            time.sleep(0.01)
        self.fail(f"status did not reach {reason!r}")

    def test_mock_http_control_and_safety_flow(self):
        status_code, page = self.request("/", pin=None)
        self.assertEqual(status_code, 200)
        self.assertIn("<!doctype html>", page.lower())

        with self.assertRaises(HTTPError) as denied:
            self.request("/api/status", pin="wrong-pin")
        self.assertEqual(denied.exception.code, 401)

        session_request = Request(
            self.base_url + "/api/status",
            headers={"X-Control-Pin": "stage1-pin"},
        )
        with urlopen(session_request, timeout=2) as response:
            session_cookie = response.headers["Set-Cookie"].split(";", 1)[0]
        cookie_request = Request(
            self.base_url + "/api/status",
            headers={"Cookie": session_cookie},
        )
        with urlopen(cookie_request, timeout=2) as response:
            self.assertEqual(response.status, 200)

        _, connected = self.request("/api/connect", {"client_id": "owner"})
        self.assertTrue(connected["status"]["connected"])
        self.assertTrue(connected["status"]["estopped"])

        _, armed = self.request("/api/arm", {"client_id": "owner"})
        self.assertFalse(armed["status"]["estopped"])

        with self.assertRaises(HTTPError) as conflict:
            self.request("/api/heartbeat", {"client_id": "other"})
        self.assertEqual(conflict.exception.code, 409)

        _, moving = self.request(
            "/api/velocity", {"client_id": "owner", "x": 0.2, "y": 0, "yaw": 0}
        )
        self.assertEqual(moving["status"]["velocity"]["x"], 0.2)
        self.request("/api/heartbeat", {"client_id": "owner"})
        timed_out = self.wait_for_reason("motion_command_timeout")
        self.assertEqual(timed_out["velocity"], {"x": 0.0, "y": 0.0, "yaw": 0.0})
        self.assertEqual(timed_out["controller_id"], "owner")

        self.request("/api/arm", {"client_id": "owner"})
        self.request(
            "/api/velocity", {"client_id": "owner", "x": 0.2, "y": 0, "yaw": 0}
        )
        _, stopped = self.request(
            "/api/velocity", {"client_id": "owner", "x": 0, "y": 0, "yaw": 0}
        )
        time.sleep(0.12)
        _, still_armed = self.request("/api/status")
        self.assertFalse(still_armed["status"]["estopped"])
        self.assertEqual(stopped["status"]["velocity"], {"x": 0.0, "y": 0.0, "yaw": 0.0})

        _, action = self.request(
            "/api/action", {"client_id": "owner", "name": "stand"}
        )
        self.assertEqual(action["status"]["motion_state"], "起立中")

        _, emergency = self.request("/api/estop", {"client_id": "observer"})
        self.assertTrue(emergency["status"]["estopped"])
        self.assertEqual(emergency["status"]["estop_reason"], "button")

        self.assertIsInstance(self.adapter, MockRobotAdapter)


if __name__ == "__main__":
    unittest.main()
