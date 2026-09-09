"""F710 X-mode input -> existing local HTTP API. No direct SDK access."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import select
import signal
import time
import uuid
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError

# Linux evdev X-input codes, independent of the optional evdev import.
ABS_X, ABS_Y, ABS_RX = 0, 1, 3
A, B, X, Y, LB, BACK, START = 304, 305, 307, 308, 310, 314, 315
RB = 311
ZERO = dict(x=0.0, y=0.0, yaw=0.0)


def normalize(value, minimum, maximum):
    if maximum <= minimum:
        raise ValueError("Invalid joystick axis range")
    value = max(-1.0, min(1.0, 2 * (value - minimum) / (maximum - minimum) - 1))
    return 0.0 if abs(value) <= 0.18 else min(1.0, (abs(value) - 0.18) / 0.82) * (1 if value > 0 else -1)


class Controls:
    def __init__(self):
        self.axes = {ABS_X: 0.0, ABS_Y: 0.0, ABS_RX: 0.0}
        self.buttons = set()
        self.last_input = float('-inf')
        self.blocked = True

    def button(self, code, value):
        rising = value == 1 and code not in self.buttons
        if value:
            self.buttons.add(code)
        else:
            self.buttons.discard(code)
        return rising

    def command(self, now):
        # No input changes for two seconds latches motion until explicit X.
        if any(self.axes.values()) and now - self.last_input > 2.0:
            self.blocked = True
        if self.blocked:
            return ZERO.copy()
        lateral = -self.axes[ABS_X] * 0.30
        # Match the existing Walk lateral start threshold.
        if lateral:
            lateral = (1 if lateral > 0 else -1) * max(0.25, abs(lateral))
        forward = -self.axes[ABS_Y]
        # Keep the existing maximum, but clear Walk's 0.2 start threshold.
        if forward:
            forward = 0.25 if forward > 0 else -0.25
        return dict(x=forward, y=lateral, yaw=-self.axes[ABS_RX] * 0.5)

    def neutral(self):
        return not any(self.axes.values())


class Api:
    def __init__(self, pin, port):
        self.pin = pin
        self.base = f'http://127.0.0.1:{port}'
        self.client_id = 'f710-' + str(uuid.uuid4())
        self.opener = build_opener(ProxyHandler({}))

    def call(self, route, body=None):
        data = None if body is None else json.dumps(dict(body, client_id=self.client_id)).encode()
        request = Request(self.base + '/api/' + route, data=data,
                          headers={'Content-Type': 'application/json', 'X-Control-Pin': self.pin})
        timeout = 10.0 if route == 'connect' else 0.2 if route == 'velocity' else 3.0
        try:
            with self.opener.open(request, timeout=timeout) as response:
                payload = json.load(response)
        except HTTPError as exc:
            try:
                error = json.load(exc).get('error', str(exc))
            except (ValueError, OSError):
                error = str(exc)
            finally:
                exc.close()
            raise RuntimeError(f'{route}: {error} (HTTP {exc.code})') from exc
        if not payload.get('ok'):
            raise RuntimeError(payload.get('error', 'API failed'))
        return payload['status']


class Controller:
    def __init__(self, api, require_start=False):
        self.api = api
        self.active = False
        self.last_report = None
        self.require_start = require_start
        self.started = not require_start

    def press(self, code, controls):
        if code == B:
            self.started = not self.require_start
            self.active = False
            controls.blocked = True
            self.api.call('estop', {})
            print('已急停并进入待命；按 START 重新开始', flush=True)
        elif not self.started and code != START:
            return
        elif self.active and RB in controls.buttons and code in (Y, A, X, BACK) and controls.neutral():
            controls.blocked = True
            name = {Y: 'bound', A: 'inv_bipedal', X: 'left_flip', BACK: 'right_flip'}[code]
            self.api.call('action', {'name': name, 'confirmed': True})
            print(f'动作已提交：{name}；摇杆移动已锁定，回中后按 X 返回行走', flush=True)
        elif code in (START, BACK) and controls.neutral():
            self.active = False
            controls.blocked = True
            if code == START:
                status = self.api.call('status')
                if not status['connected']:
                    self.api.call('connect', {})
                self.started = True
                print('连接已就绪；按 BACK 解锁，再按 Y 起立、X 行走', flush=True)
            else:
                self.api.call('arm', {})
                self.active = True
                print('已解锁；按 Y 起立，按 X 开放摇杆行走', flush=True)
        elif self.active and controls.neutral() and code in (A, X, Y):
            controls.blocked = True
            self.api.call('action', {'name': {A: 'sit', X: 'walk', Y: 'stand'}[code]})
            if code == X:
                controls.blocked = False
                controls.last_input = time.monotonic()
                print('行走已启用：直接推动摇杆，回中停止；B 急停', flush=True)

    def tick(self, controls, now):
        if self.active:
            command = controls.command(now)
            report = (controls.blocked, LB in controls.buttons, tuple(command.values()))
            if report != self.last_report:
                if controls.blocked:
                    print('运动输入已锁定：摇杆回中后按 X；持续无新输入 2 秒会停止', flush=True)
                else:
                    print(f'发送速度 x={command["x"]:.3f} y={command["y"]:.3f} yaw={command["yaw"]:.3f}', flush=True)
                self.last_report = report
            status = self.api.call('velocity', command)
            if status['estopped'] or status['controller_id'] != self.api.client_id:
                self.active = False
                controls.blocked = True

    def stop(self):
        if self.active:
            self.active = False
            self.api.call('velocity', ZERO)

    def recover(self, controls, error):
        controls.blocked = True
        try:
            self.stop()
        except (OSError, RuntimeError, ValueError):
            pass
        self.active = False
        print(f'请求失败：{error}。已暂停运动，程序仍运行。未连接请按 START；连接后按 BACK。B 急停仍可用。', flush=True)


def main():
    parser = argparse.ArgumentParser(description='Mymooo F710 本地手柄控制（X 模式）')
    parser.add_argument('--device', help='指定 /dev/input/eventN；默认自动查找 F710')
    parser.add_argument('--list', action='store_true', help='列出输入设备并退出')
    parser.add_argument('--control', action='store_true', help='启用 HTTP 控制；默认仅检查输入')
    parser.add_argument('--port', type=int, default=8088)
    parser.add_argument('--standby', action='store_true', help='后台待命：只从环境读取 PIN，START 后才接受解锁')
    args = parser.parse_args()
    try:
        from evdev import InputDevice, list_devices
    except ImportError:
        parser.exit(1, '请在树莓派项目虚拟环境安装 requirements-gamepad.txt\n')
    paths = [args.device] if args.device else list_devices()
    devices = []
    for path in paths:
        try:
            device = InputDevice(path)
        except OSError as exc:
            print(f'{path}: {exc}')
            continue
        if args.list:
            print(f'{device.path}: {device.name}')
            device.close()
        elif args.device or 'F710' in device.name.upper():
            devices.append(device)
        else:
            device.close()
    if args.list:
        return
    if len(devices) != 1:
        for device in devices:
            device.close()
        parser.exit(1, '需恰好一个 F710；请使用 --list 后以 --device 指定设备\n')
    device = devices[0]
    controller = None
    running = True

    def stop_signal(*_):
        nonlocal running
        running = False

    try:
        axes = {code: device.absinfo(code) for code in (ABS_X, ABS_Y, ABS_RX)}
        keys = device.capabilities().get(1, [])
        if any(info is None or info.max <= info.min for info in axes.values()) or not {A, B, X, Y, LB, BACK, START}.issubset(keys):
            raise RuntimeError('输入映射不匹配：请设置 F710 为 X 模式并关闭 MODE 灯')
        controls = Controls()
        controls.buttons = set(device.active_keys())
        for code, info in axes.items():
            controls.axes[code] = normalize(info.value, info.min, info.max)
        if args.control:
            pin = os.environ.get('MYMOOO_PIN') or os.environ.get('ROBOTDOG_PIN')
            if not pin and args.standby:
                raise RuntimeError('后台服务缺少 MYMOOO_PIN/ROBOTDOG_PIN')
            if not pin:
                pin = getpass.getpass('控制 PIN: ')
            device.grab()
            controller = Controller(Api(pin, args.port), require_start=args.standby)
        signal.signal(signal.SIGINT, stop_signal)
        signal.signal(signal.SIGTERM, stop_signal)
        print(f'{device.path}: {device.name}; ' + ('控制模式' if controller else '输入检查模式（不发送 HTTP）'))
        print('START 连接 / BACK 解锁 / Y 起立 / X 行走（摇杆直接移动）/ A 坐下 / B 急停')
        print('RB+Y 跳跃步态 / RB+A 倒立 / RB+X 左侧翻 / RB+BACK 右侧翻；需摇杆回中且已解锁')
        next_tick = time.monotonic()
        while running:
            ready, _, _ = select.select([device], [], [], max(0, next_tick - time.monotonic()))
            if ready:
                try:
                    events = list(device.read())
                except BlockingIOError:
                    events = []
                for event in events:
                    if event.type == 0 and event.code == 3:
                        raise RuntimeError('输入事件丢失，请重新启动并解锁')
                    # Do not treat SYN/auto-repeat as proof of fresh operator input.
                    if event.type == 3 and event.code in axes:
                        info = axes[event.code]
                        controls.axes[event.code] = normalize(event.value, info.min, info.max)
                        controls.last_input = time.monotonic()
                    elif event.type == 1 and event.code in keys and event.value in (0, 1):
                        controls.last_input = time.monotonic()
                        if controls.button(event.code, event.value) and controller:
                            try:
                                controller.press(event.code, controls)
                            except (OSError, RuntimeError, ValueError) as exc:
                                controller.recover(controls, exc)
                    if not controller and event.type in (1, 3):
                        print(f'type={event.type} code={event.code} value={event.value}', flush=True)
            now = time.monotonic()
            if now >= next_tick:
                if controller:
                    try:
                        controller.tick(controls, now)
                    except (OSError, RuntimeError, ValueError) as exc:
                        controller.recover(controls, exc)
                next_tick = time.monotonic() + 0.05
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'手柄控制停止: {exc}')
        return 1
    finally:
        if controller:
            try:
                controller.stop()
            except Exception as exc:
                print(f'停止请求未确认，服务器运动 TTL 将兜底: {exc}')
        device.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
