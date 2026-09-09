import unittest
import io
from urllib.error import HTTPError
from unittest.mock import Mock, patch
from gamepad import Controls, Controller, Api, ABS_Y, B, X, Y, A, BACK, START, RB, ZERO
from server import ControlService, MockRobotAdapter, MymoooRobotAdapter

class GamepadTests(unittest.TestCase):
    def test_standby_requires_start_and_b_returns_to_standby(self):
        api = Mock()
        api.call.return_value = {'connected': True}
        ctl = Controller(api, require_start=True)
        c = Controls()
        for key in (BACK, X, Y, A):
            ctl.press(key, c)
        ctl.tick(c, 1)
        api.call.assert_not_called()
        ctl.press(START, c)
        ctl.press(BACK, c)
        self.assertTrue(ctl.active)
        ctl.press(B, c)
        self.assertFalse(ctl.started)
        api.call.reset_mock()
        ctl.press(BACK, c)
        api.call.assert_not_called()
    def test_idle_center_keeps_walk_enabled(self):
        c = Controls()
        c.blocked = False
        c.last_input = 1
        self.assertEqual(c.command(100), ZERO)
        self.assertFalse(c.blocked)
        c.last_input = 101
        c.axes[ABS_Y] = -1
        self.assertEqual(c.command(101)['x'], .25)
    def test_http_error_includes_backend_reason(self):
        api = Api('test', 8088)
        api.opener = Mock()
        api.opener.open.side_effect = HTTPError('http://local', 503, 'Unavailable', {}, io.BytesIO(b'{"error":"connect first"}'))
        with self.assertRaisesRegex(RuntimeError, 'connect first'):
            api.call('arm', {})

    def test_recover_keeps_controller_available_but_inactive(self):
        c = Controls()
        ctl = Controller(Mock())
        ctl.active = True
        ctl.recover(c, RuntimeError('test'))
        self.assertFalse(ctl.active)
        self.assertTrue(c.blocked)
        ctl.press(B, c)
        ctl.api.call.assert_called_with('estop', {})

    def test_repeated_start_does_not_reconnect(self):
        api = Mock()
        api.call.return_value = {'connected': True}
        ctl = Controller(api)
        ctl.press(START, Controls())
        api.call.assert_called_once_with('status')

    def test_service_connect_is_idempotent(self):
        adapter = MockRobotAdapter('unused')
        adapter.connect = Mock(wraps=adapter.connect)
        s = ControlService(adapter, 'mock', 'unused')
        try:
            s.connect('test')
            s.connect('test')
            adapter.connect.assert_called_once()
        finally:
            s.close()
    def test_walk_without_lb_and_center_stop(self):
        c = Controls()
        ctl = Controller(Mock())
        c.axes[ABS_Y] = -1
        self.assertEqual(c.command(0), ZERO)
        c.axes[ABS_Y] = 0
        ctl.active = True
        with patch('gamepad.time.monotonic', return_value=10):
            ctl.press(X, c)
        c.axes[ABS_Y] = -0.1
        self.assertEqual(c.command(11)['x'], 0.25)
        c.axes[ABS_Y] = 0
        self.assertEqual(c.command(11), ZERO)

    def test_stale_latches(self):
        c = Controls()
        c.blocked = False
        c.last_input = 10
        c.axes[ABS_Y] = -1
        self.assertEqual(c.command(12.01), ZERO)
        c.last_input = 13
        self.assertEqual(c.command(13), ZERO)

    def test_connect_arm_still_locked(self):
        c = Controls()
        ctl = Controller(Mock())
        ctl.api.call.return_value = {'connected': False}
        ctl.press(START, c)
        ctl.press(BACK, c)
        self.assertTrue(c.blocked)

    def test_neutral_required(self):
        c = Controls()
        c.axes[ABS_Y] = 1
        api = Mock()
        ctl = Controller(api)
        ctl.active = True
        for code in (X, Y, A, BACK, START):
            ctl.press(code, c)
        api.call.assert_not_called()

    def test_combos(self):
        for key, name in ((Y, 'bound'), (A, 'inv_bipedal'), (X, 'left_flip'), (BACK, 'right_flip')):
            c = Controls()
            c.buttons.add(RB)
            api = Mock()
            ctl = Controller(api)
            ctl.active = True
            ctl.press(key, c)
            api.call.assert_called_once_with('action', {'name': name, 'confirmed': True})
            self.assertTrue(c.blocked)

    def test_b_always_estops(self):
        c = Controls()
        c.axes[ABS_Y] = 1
        api = Mock()
        ctl = Controller(api)
        ctl.press(B, c)
        api.call.assert_called_once_with('estop', {})
        self.assertFalse(ctl.active)

    def test_timeout_routes(self):
        api = Api('test', 8088)
        api.opener = Mock()
        api.opener.open.side_effect = TimeoutError
        for route, timeout in (('connect', 10), ('action', 3), ('velocity', .2)):
            with self.assertRaises(TimeoutError):
                api.call(route, {})
            self.assertEqual(api.opener.open.call_args.kwargs['timeout'], timeout)

    def test_sdk_dispatch_no_hardware(self):
        adapter = MymoooRobotAdapter('unused')
        adapter.connected = True
        adapter._motion = Mock()
        for name, method in (('bound', 'setBound'), ('inv_bipedal', 'setInvBipedal'), ('left_flip', 'setLeftFlip'), ('right_flip', 'setRightFlip')):
            adapter.action(name)
            getattr(adapter._motion, method).assert_called_once_with()

    def test_service_confirmation(self):
        s = ControlService(MockRobotAdapter('unused'), 'mock', 'unused')
        try:
            s.connect('test')
            s.arm('test')
            for name in ('bound', 'inv_bipedal', 'left_flip', 'right_flip'):
                with self.assertRaises(ValueError):
                    s.action('test', name)
                s.action('test', name, confirmed=True)
                self.assertEqual(s.velocity.x, 0)
        finally:
            s.close()
