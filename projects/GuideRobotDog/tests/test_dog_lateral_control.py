import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import ControlService, MockRobotAdapter  # noqa: E402


class DogLateralControlTests(unittest.TestCase):
    def test_page_exposes_explicit_left_and_right_strafe_buttons(self):
        page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-axis="y" data-direction="1"', page)
        self.assertIn('data-axis="y" data-direction="-1"', page)
        self.assertIn("左移", page)
        self.assertIn("右移", page)
        self.assertIn('KeyA: ["y", 1]', script)
        self.assertIn('KeyD: ["y", -1]', script)
        self.assertIn("command.y *= 0.35 * state.speed", script)
        self.assertIn("Math.abs(command.y) < 0.25", script)

    def test_backend_forwards_positive_and_negative_lateral_velocity(self):
        adapter = MockRobotAdapter("10.21.20.1")
        service = ControlService(adapter, "mock", "10.21.20.1")
        try:
            service.connect("test-client")
            service.arm("test-client")
            left = service.set_velocity("test-client", 0.0, 0.2, 0.0)
            self.assertEqual(left.y, 0.2)
            self.assertEqual(adapter.velocity.y, 0.2)
            right = service.set_velocity("test-client", 0.0, -0.2, 0.0)
            self.assertEqual(right.y, -0.2)
            self.assertEqual(adapter.velocity.y, -0.2)
        finally:
            service.stop_event.set()
            adapter.disconnect()


if __name__ == "__main__":
    unittest.main()
