import sys
import time
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import ControlService, MockRobotAdapter, Velocity  # noqa: E402


class RecordingMockAdapter(MockRobotAdapter):
    """Mock adapter that refuses every command except zero-speed and damping."""

    def __init__(self, robot_ip: str) -> None:
        super().__init__(robot_ip)
        self.zero_velocity_calls = 0
        self.damping_calls = 0

    def set_velocity(self, velocity):
        if velocity.x != 0.0 or velocity.y != 0.0 or velocity.yaw != 0.0:
            raise AssertionError("安全测试禁止发送非零速度")
        self.zero_velocity_calls += 1
        super().set_velocity(velocity)

    def action(self, name: str) -> None:
        if name != "damping":
            raise AssertionError(f"安全测试禁止调用运动动作: {name}")
        self.damping_calls += 1
        super().action(name)


class FaultInjectingAdapter(MockRobotAdapter):
    """Record the adapter boundary while allowing precise injected failures."""

    def __init__(self, robot_ip: str) -> None:
        super().__init__(robot_ip)
        self.velocity_calls = []
        self.action_calls = []
        self.fail_nonzero_velocity = False
        self.fail_all_velocity = False
        self.fail_action_name = None
        self.fail_telemetry = False

    def set_velocity(self, velocity):
        self.velocity_calls.append(velocity)
        if self.fail_all_velocity:
            raise RuntimeError("zero link failed")
        if self.fail_nonzero_velocity and velocity != Velocity():
            raise RuntimeError("drive link failed")
        super().set_velocity(velocity)

    def action(self, name: str) -> None:
        self.action_calls.append(name)
        if name == self.fail_action_name:
            raise RuntimeError("action link failed")
        super().action(name)

    def telemetry(self):
        if self.fail_telemetry:
            raise RuntimeError("telemetry link failed")
        return super().telemetry()


def wait_until(predicate, timeout=0.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class ControlStateTests(unittest.TestCase):
    def setUp(self):
        self.adapter = RecordingMockAdapter("10.21.20.1")
        self.service = ControlService(self.adapter, "mock", "10.21.20.1")
        self.service.CONTROLLER_TIMEOUT_SECONDS = 0.08
        self.service.MOTION_COMMAND_TTL_SECONDS = 1.0
        self.service.connect("client-a")

    def tearDown(self):
        # Stop only the mock watchdog. Do not invoke ControlService.close(),
        # because teardown must not exercise any adapter command.
        self.service.stop_event.set()
        self.adapter.disconnect()

    def test_startup_is_estopped(self):
        status = self.service.status()
        self.assertTrue(status["connected"])
        self.assertTrue(status["estopped"])
        self.assertEqual(status["estop_reason"], "startup")

    def test_arm_is_software_only_and_heartbeat_keeps_it_cleared(self):
        self.service.arm("client-a")
        self.assertFalse(self.service.estopped)
        self.assertEqual(self.service.estop_reason, "none")
        self.assertEqual(self.adapter.zero_velocity_calls, 0)
        self.assertEqual(self.adapter.damping_calls, 0)
        for _ in range(3):
            self.service.heartbeat("client-a")
            time.sleep(0.03)
        self.assertFalse(self.service.estopped)

    def test_no_controller_does_not_trigger_watchdog_while_idle(self):
        self.service.arm("client-a")
        self.service._release_controller()
        time.sleep(0.14)
        self.assertFalse(self.service.estopped)
        self.assertEqual(self.service.estop_reason, "none")
        self.assertEqual(self.adapter.zero_velocity_calls, 0)
        self.assertEqual(self.adapter.damping_calls, 0)

    def test_lost_controller_stops_without_damping_or_disconnect(self):
        self.adapter.motion_state = 1  # Simulated standing, no hardware action.
        self.service.velocity = Velocity(x=0.2)
        self.adapter.velocity = Velocity(x=0.2)
        self.service.last_velocity_at = time.monotonic()
        self.service.arm("client-a")
        time.sleep(0.14)
        status = self.service.status()
        self.assertTrue(status["estopped"])
        self.assertEqual(status["estop_reason"], "watchdog")
        self.assertIsNone(status["controller_id"])
        self.assertFalse(status["controller_active"])
        self.assertEqual(self.adapter.zero_velocity_calls, 1)
        self.assertEqual(self.adapter.damping_calls, 0)
        self.assertEqual(self.adapter.motion_state, 1)
        self.assertTrue(status["connected"])
        self.assertEqual(status["velocity"], {"x": 0.0, "y": 0.0, "yaw": 0.0})
        self.assertEqual(self.adapter.velocity, Velocity())
        self.assertEqual(status["watchdog_action"], "zero_velocity_keep_mode")
        # A returning heartbeat must not restart an old movement.
        self.service.heartbeat("client-a")
        self.assertTrue(self.service.estopped)
        with self.assertRaisesRegex(RuntimeError, "急停已锁定"):
            self.service.set_velocity("client-a", 0.2, 0, 0)
        self.service.arm("client-a")
        self.assertFalse(self.service.estopped)
        self.assertTrue(self.adapter.connected)
        self.assertEqual(self.adapter.zero_velocity_calls, 1)
        self.assertEqual(self.adapter.damping_calls, 0)

    def test_explicit_emergency_stop_still_damps_after_timeout_and_is_idempotent(self):
        self.service._trigger_estop("watchdog", release_controller=True)
        self.assertEqual(self.adapter.damping_calls, 0)
        for _ in range(2):
            self.service.engage_estop()
            self.assertTrue(self.service.estopped)
            self.assertEqual(self.service.estop_reason, "button")
        self.assertEqual(self.adapter.damping_calls, 2)
        self.assertTrue(self.adapter.connected)

    def test_button_estop_then_second_click_clears_without_robot_call(self):
        self.service.arm("client-a")
        self.service.action("client-a", "estop")
        self.assertTrue(self.service.estopped)
        self.assertEqual(self.service.estop_reason, "button")
        safety_calls = (self.adapter.zero_velocity_calls, self.adapter.damping_calls)

        self.service.action("client-a", "estop")
        self.assertFalse(self.service.estopped)
        self.assertEqual(self.service.estop_reason, "none")
        self.assertEqual(
            (self.adapter.zero_velocity_calls, self.adapter.damping_calls),
            safety_calls,
        )

    def test_status_contains_debug_fields(self):
        status = self.service.status()
        expected = {
            "connected",
            "estopped",
            "estop_reason",
            "controller_active",
            "controller_id",
            "last_velocity_at",
            "controller_seen_at",
        }
        self.assertTrue(expected.issubset(status))

    def test_software_test_estop_never_calls_adapter(self):
        self.service.set_test_estop(True)
        self.assertTrue(self.service.estopped)
        self.assertEqual(self.service.estop_reason, "test")
        self.service.set_test_estop(False)
        self.assertFalse(self.service.estopped)
        self.assertEqual(self.adapter.zero_velocity_calls, 0)
        self.assertEqual(self.adapter.damping_calls, 0)


class MotionCommandSafetyTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FaultInjectingAdapter("10.21.20.1")
        self.service = ControlService(self.adapter, "mock", "10.21.20.1")
        self.service.MOTION_COMMAND_TTL_SECONDS = 0.08
        self.service.CONTROLLER_TIMEOUT_SECONDS = 0.4
        self.service.connect("client-a")
        self.service.arm("client-a")

    def tearDown(self):
        self.service.stop_event.set()
        self.adapter.disconnect()

    def test_repeated_nonzero_velocity_refreshes_motion_ttl(self):
        self.service.set_velocity("client-a", 0.2, 0, 0)
        time.sleep(0.05)
        self.service.set_velocity("client-a", 0.2, 0, 0)
        time.sleep(0.05)
        self.assertFalse(self.service.estopped)

        self.assertTrue(wait_until(lambda: self.service.estopped))
        status = self.service.status()
        self.assertEqual(status["estop_reason"], "motion_command_timeout")
        self.assertEqual(status["velocity"], {"x": 0.0, "y": 0.0, "yaw": 0.0})
        self.assertEqual(status["controller_id"], "client-a")
        self.assertTrue(status["controller_active"])

    def test_zero_velocity_cancels_motion_ttl(self):
        self.service.set_velocity("client-a", 0.2, 0, 0)
        time.sleep(0.03)
        self.service.set_velocity("client-a", 0, 0, 0)
        time.sleep(0.12)

        self.assertFalse(self.service.estopped)
        self.assertEqual(self.service.estop_reason, "none")
        self.assertEqual(self.service.velocity, Velocity())

    def test_heartbeat_does_not_refresh_motion_ttl(self):
        self.service.set_velocity("client-a", 0.2, 0, 0)
        for _ in range(6):
            self.service.heartbeat("client-a")
            time.sleep(0.02)

        self.assertTrue(wait_until(lambda: self.service.estopped))
        self.assertEqual(self.service.estop_reason, "motion_command_timeout")
        self.assertEqual(self.service.controller_id, "client-a")

    def test_idle_controller_lease_expires_independently_of_motion_ttl(self):
        self.service.CONTROLLER_TIMEOUT_SECONDS = 0.08
        self.service.MOTION_COMMAND_TTL_SECONDS = 0.02

        self.assertTrue(wait_until(lambda: self.service.estopped, timeout=0.3))
        self.assertEqual(self.service.estop_reason, "watchdog")
        self.assertIsNone(self.service.controller_id)

    def test_velocity_exception_latches_fault_and_attempts_zero(self):
        self.adapter.fail_nonzero_velocity = True

        with self.assertRaisesRegex(RuntimeError, "drive link failed"):
            self.service.set_velocity("client-a", 0.2, 0, 0)

        status = self.service.status()
        self.assertTrue(status["estopped"])
        self.assertEqual(status["estop_reason"], "adapter_error")
        self.assertIn("set_velocity: drive link failed", status["last_error"])
        self.assertEqual(self.adapter.velocity_calls[-1], Velocity())

        self.adapter.fail_nonzero_velocity = False
        with self.assertRaisesRegex(RuntimeError, "急停已锁定"):
            self.service.set_velocity("client-a", 0.2, 0, 0)

    def test_action_exception_latches_fault_and_attempts_zero(self):
        self.adapter.fail_action_name = "stand"

        with self.assertRaisesRegex(RuntimeError, "action link failed"):
            self.service.action("client-a", "stand")

        status = self.service.status()
        self.assertTrue(status["estopped"])
        self.assertEqual(status["estop_reason"], "adapter_error")
        self.assertIn("action stand: action link failed", status["last_error"])
        self.assertEqual(self.adapter.velocity_calls[-1], Velocity())

    def test_telemetry_exception_latches_fault_and_arm_clears_it(self):
        self.adapter.fail_telemetry = True
        status = self.service.status()

        self.assertTrue(status["estopped"])
        self.assertEqual(status["estop_reason"], "adapter_error")
        self.assertIn("telemetry: telemetry link failed", status["last_error"])
        self.assertEqual(self.adapter.velocity_calls[-1], Velocity())

        self.adapter.fail_telemetry = False
        self.service.arm("client-a")
        recovered = self.service.status()
        self.assertFalse(recovered["estopped"])
        self.assertEqual(recovered["estop_reason"], "none")
        self.assertIsNone(recovered["last_error"])

    def test_safe_stop_failure_keeps_original_command_error(self):
        self.adapter.fail_all_velocity = True

        with self.assertRaisesRegex(RuntimeError, "zero link failed"):
            self.service.set_velocity("client-a", 0.2, 0, 0)

        self.assertTrue(self.service.estopped)
        self.assertEqual(self.service.estop_reason, "adapter_error")
        self.assertIn("set_velocity: zero link failed", self.service.last_error)
        self.assertIn("safe stop failed: zero link failed", self.service.last_error)

    def test_explicit_estop_rejects_followup_nonzero_velocity(self):
        self.service.engage_estop()

        with self.assertRaisesRegex(RuntimeError, "急停已锁定"):
            self.service.set_velocity("client-a", 0.2, 0, 0)


if __name__ == "__main__":
    unittest.main()
