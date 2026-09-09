from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
import signal
import threading
import time
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"


MOTION_STATES = {
    0: "趴卧",
    1: "起立中",
    2: "阻尼",
    3: "坐下",
    6: "运动中",
}

GAITS = {
    0: "行走",
    3: "双足",
    4: "侧翻",
    6: "节奏步态",
    7: "姿态跟踪",
    8: "奔跑",
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


@dataclass
class Velocity:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0


class RobotAdapter(Protocol):
    connected: bool

    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def set_velocity(self, velocity: Velocity) -> None: ...
    def action(self, name: str) -> None: ...
    def telemetry(self) -> dict[str, Any]: ...


class MockRobotAdapter:
    def __init__(self, robot_ip: str) -> None:
        self.robot_ip = robot_ip
        self.connected = False
        self.started_at = time.monotonic()
        self.velocity = Velocity()
        self.motion_state = 0
        self.gait = 0
        self.battery = 86.0

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False
        self.velocity = Velocity()

    def set_velocity(self, velocity: Velocity) -> None:
        if not self.connected:
            raise RuntimeError("机器人尚未连接")
        self.velocity = velocity
        if any(abs(v) > 0.001 for v in asdict(velocity).values()):
            self.motion_state = 6

    def action(self, name: str) -> None:
        if not self.connected:
            raise RuntimeError("机器人尚未连接")
        if name == "stand":
            self.motion_state = 1
        elif name == "sit":
            self.motion_state = 3
        elif name == "damping":
            self.motion_state = 2
            self.velocity = Velocity()
        elif name == "walk":
            self.gait = 0
        elif name == "running":
            self.gait = 8
        elif name in {"bound", "inv_bipedal", "left_flip", "right_flip"}:
            self.gait = {"bound": 6, "inv_bipedal": 3, "left_flip": 4, "right_flip": 4}[name]
        elif name == "zero_positions":
            self.motion_state = 0
        else:
            raise ValueError(f"不支持的动作: {name}")

    def telemetry(self) -> dict[str, Any]:
        if self.connected:
            speed = abs(self.velocity.x) + abs(self.velocity.y) + abs(self.velocity.yaw) * 0.2
            self.battery = max(0.0, self.battery - speed * 0.0008)
        phase = time.monotonic() - self.started_at
        return {
            "battery": round(self.battery, 1),
            "motion_state": self.motion_state,
            "gait": self.gait,
            "imu_rpy": [round(0.01 * __import__("math").sin(phase), 3), 0.0, 0.0],
            "leg_velocity": [self.velocity.x, self.velocity.y, 0.0],
            "max_motor_temperature": 39.0,
        }


class MymoooRobotAdapter:
    def __init__(self, robot_ip: str) -> None:
        self.robot_ip = robot_ip
        self.connected = False
        self._motion: Any = None

    def connect(self) -> bool:
        if self.connected and self._motion is not None:
            return True
        try:
            import bpx_sdk  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "未安装官方 bpx_sdk。请先执行 scripts/install-bpx-sdk.sh"
            ) from exc

        motion = bpx_sdk.MotionLevelControl()
        motion.setRobotIp(self.robot_ip)
        motion.setRobotStateUploadPort(bpx_sdk.DEFAULT_CLIENT_ROBOT_STATE_UDP_PORT)
        motion.setTcpLocalPort(0)
        motion.setRobotStateUploadRate(20)
        motion.setMotionCommandRate(20)
        if not motion.connect():
            raise RuntimeError(f"无法连接机器狗（{self.robot_ip}），请检查网线和静态 IP")
        motion.setVelocityControlFlag(True)
        self._motion = motion
        self.connected = True
        return True

    def disconnect(self) -> None:
        if self._motion is not None:
            try:
                self._motion.setVelocity(0.0, 0.0, 0.0)
                self._motion.disconnect()
            finally:
                self._motion = None
        self.connected = False

    def _require_motion(self) -> Any:
        if not self.connected or self._motion is None:
            raise RuntimeError("机器人尚未连接")
        return self._motion

    def set_velocity(self, velocity: Velocity) -> None:
        self._require_motion().setVelocity(velocity.x, velocity.y, velocity.yaw)

    def action(self, name: str) -> None:
        motion = self._require_motion()
        special = {"bound": "setBound", "inv_bipedal": "setInvBipedal", "left_flip": "setLeftFlip", "right_flip": "setRightFlip"}
        if name in special:
            getattr(motion, special[name])()
            return
        methods = {
            "stand": motion.setStandUp,
            "sit": motion.setSitDown,
            "damping": motion.setDamping,
            "release_estop": motion.setDamping,
            "walk": motion.setWalk,
            "running": motion.setRunning,
            "zero_positions": motion.setZeroPositionsFlag,
        }
        if name not in methods:
            raise ValueError(f"不支持的动作: {name}")
        methods[name]()

    def telemetry(self) -> dict[str, Any]:
        if not self.connected or self._motion is None:
            return {}
        motion = self._motion
        odom = motion.getLegOdom() or {}
        temperatures = motion.getMotorTemperature() or []
        return {
            "battery": motion.getBatteryLevel(),
            "motion_state": motion.getCurrentMotionState(),
            "gait": motion.getCurrentGait(),
            "imu_rpy": motion.getImuRpy(),
            "leg_velocity": odom.get("velocity_body") if isinstance(odom, dict) else None,
            "max_motor_temperature": max(temperatures) if temperatures else None,
        }


class ControlService:
    CONTROLLER_TIMEOUT_SECONDS = 3.0
    MOTION_COMMAND_TTL_SECONDS = 0.30

    def __init__(self, adapter: RobotAdapter, mode: str, robot_ip: str) -> None:
        self.adapter = adapter
        self.mode = mode
        self.robot_ip = robot_ip
        self.estopped = True
        self.estop_reason = "startup"
        self.velocity = Velocity()
        self.controller_id: str | None = None
        self.controller_seen_at = 0.0
        self.last_velocity_at = 0.0
        self.last_error: str | None = None
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.watchdog = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog.start()

    def _claim(self, client_id: str) -> None:
        if not client_id or len(client_id) > 128:
            raise ValueError("无效的客户端标识")
        now = time.monotonic()
        if (
            self.controller_id
            and self.controller_id != client_id
            and now - self.controller_seen_at < self.CONTROLLER_TIMEOUT_SECONDS
        ):
            raise PermissionError("已有另一台设备正在控制")
        self.controller_id = client_id
        self.controller_seen_at = now

    def connect(self, client_id: str) -> None:
        with self.lock:
            self._claim(client_id)
            if self.adapter.connected:
                return
            self.adapter.connect()
            self.estopped = True
            self.estop_reason = "startup"
            self.last_error = None

    def disconnect(self, client_id: str) -> None:
        with self.lock:
            self._claim(client_id)
            self.estopped = True
            self.estop_reason = "disconnect"
            self._safe_stop(damping=True)
            self.adapter.disconnect()
            self._release_controller()

    def arm(self, client_id: str) -> None:
        with self.lock:
            self._claim(client_id)
            if not self.adapter.connected:
                raise RuntimeError("请先连接机器人")
            self.estopped = False
            self.estop_reason = "none"
            self.last_error = None

    def heartbeat(self, client_id: str) -> None:
        """Refresh the controller lease without sending a robot command."""
        with self.lock:
            self._claim(client_id)

    def set_velocity(self, client_id: str, x: float, y: float, yaw: float) -> Velocity:
        with self.lock:
            self._claim(client_id)
            if self.estopped:
                raise RuntimeError("急停已锁定，请先解除急停")
            velocity = Velocity(
                x=round(clamp(x, -0.8, 0.8), 3),
                y=round(clamp(y, -0.35, 0.35), 3),
                yaw=round(clamp(yaw, -1.2, 1.2), 3),
            )
            self._apply_velocity(velocity, "set_velocity")
            return velocity

    def action(self, client_id: str, name: str, confirmed: bool = False) -> None:
        with self.lock:
            self._claim(client_id)
            if name == "estop":
                if self.estopped:
                    if not self.adapter.connected:
                        raise RuntimeError("请先连接机器人")
                    # Clearing an estop is a software-only transition.
                    self.estopped = False
                    self.estop_reason = "none"
                else:
                    self._trigger_estop("button", release_controller=False)
                return
            if self.estopped:
                raise RuntimeError("急停已锁定，请先解除急停")
            if name == "zero_positions" and not confirmed:
                raise ValueError("关节归零需要确认标准趴卧姿态")
            if name in {"bound", "inv_bipedal", "left_flip", "right_flip"} and not confirmed:
                raise ValueError("特殊动作需要明确确认")
            if name in {"stand", "sit", "damping", "zero_positions", "bound", "inv_bipedal", "left_flip", "right_flip"}:
                self._apply_velocity(Velocity(), "pre-action stop")
            self._apply_action(name, f"action {name}")

    def set_test_estop(self, engaged: bool) -> None:
        """Software-only estop transition; never calls the robot adapter."""
        with self.lock:
            if self.mode != "mock":
                raise RuntimeError("纯软件急停测试接口仅允许在 mock 模式使用")
            self.estopped = bool(engaged)
            self.estop_reason = "test" if engaged else "none"

    def _release_controller(self) -> None:
        self.controller_id = None
        self.controller_seen_at = 0.0

    def engage_estop(self) -> None:
        """An emergency button never toggles back to enabled or claims a lease."""
        with self.lock:
            self._trigger_estop("button", release_controller=True)

    def _trigger_estop(self, reason: str, release_controller: bool) -> None:
        self.estopped = True
        self.estop_reason = reason
        # Loss of the web controller must stop locomotion, not change the
        # robot's posture/mode or tear down its SDK connection. Explicit
        # emergency stop / disconnect / shutdown still request damping.
        self._safe_stop(damping=reason not in {"watchdog", "motion_command_timeout"})
        if release_controller:
            self._release_controller()

    def _apply_velocity(
        self,
        velocity: Velocity,
        operation: str,
        latch_on_error: bool = True,
    ) -> None:
        """Single adapter boundary for every velocity command."""
        try:
            self.adapter.set_velocity(velocity)
        except Exception as exc:
            if latch_on_error:
                self._latch_adapter_fault(operation, exc)
            raise
        self.velocity = velocity
        self.last_velocity_at = (
            0.0 if velocity == Velocity() else time.monotonic()
        )

    def _apply_action(
        self,
        name: str,
        operation: str,
        latch_on_error: bool = True,
    ) -> None:
        try:
            self.adapter.action(name)
        except Exception as exc:
            if latch_on_error:
                self._latch_adapter_fault(operation, exc)
            raise

    def _latch_adapter_fault(self, operation: str, exc: Exception) -> None:
        original_error = f"{operation}: {exc}"
        already_latched = self.estopped and self.estop_reason == "adapter_error"
        self.estopped = True
        self.estop_reason = "adapter_error"
        self.velocity = Velocity()
        self.last_velocity_at = 0.0
        self.last_error = original_error
        if not self.adapter.connected or already_latched:
            return
        try:
            self._apply_velocity(
                Velocity(), "safe stop", latch_on_error=False
            )
        except Exception as stop_exc:
            self.last_error = (
                f"{original_error}; safe stop failed: {stop_exc}"
            )

    def _safe_stop(self, damping: bool) -> None:
        self.velocity = Velocity()
        self.last_velocity_at = 0.0
        if not self.adapter.connected:
            return
        errors = []
        try:
            self._apply_velocity(
                self.velocity, "safe stop", latch_on_error=False
            )
        except Exception as exc:  # Safety path must remain best effort.
            errors.append(f"safe stop failed: {exc}")
        if damping:
            try:
                self._apply_action(
                    "damping", "safe damping", latch_on_error=False
                )
            except Exception as exc:  # Safety path must remain best effort.
                errors.append(f"safe damping failed: {exc}")
        if errors:
            self.last_error = "; ".join(errors)

    def _watchdog_loop(self) -> None:
        while not self.stop_event.wait(0.05):
            with self.lock:
                # With no controller there is no heartbeat to supervise. An
                # idle, just-unlocked robot must therefore remain unlocked.
                if self.controller_id is None or self.estopped:
                    continue
                motion_command_lost = (
                    self.velocity != Velocity()
                    and self.last_velocity_at > 0.0
                    and time.monotonic() - self.last_velocity_at
                    > self.MOTION_COMMAND_TTL_SECONDS
                )
                if motion_command_lost:
                    self._trigger_estop(
                        "motion_command_timeout", release_controller=False
                    )
                    continue
                controller_lost = (
                    time.monotonic() - self.controller_seen_at
                    > self.CONTROLLER_TIMEOUT_SECONDS
                )
                if controller_lost:
                    self._trigger_estop("watchdog", release_controller=True)

    def status(self) -> dict[str, Any]:
        with self.lock:
            try:
                telemetry = self.adapter.telemetry()
                if self.estop_reason != "adapter_error":
                    self.last_error = None
            except Exception as exc:
                telemetry = {}
                self._latch_adapter_fault("telemetry", exc)
            motion_state = telemetry.get("motion_state")
            gait = telemetry.get("gait")
            return {
                "connected": bool(self.adapter.connected),
                "mode": self.mode,
                "robot_ip": self.robot_ip,
                "estopped": self.estopped,
                "estop_reason": self.estop_reason,
                "velocity": asdict(self.velocity),
                "controller_active": bool(
                    self.controller_id
                    and time.monotonic() - self.controller_seen_at
                    < self.CONTROLLER_TIMEOUT_SECONDS
                ),
                "controller_id": self.controller_id,
                "last_velocity_at": self.last_velocity_at,
                "controller_seen_at": self.controller_seen_at,
                "motion_state": MOTION_STATES.get(motion_state, str(motion_state) if motion_state is not None else "--"),
                "gait": GAITS.get(gait, str(gait) if gait is not None else "--"),
                "battery": telemetry.get("battery"),
                "imu_rpy": telemetry.get("imu_rpy"),
                "leg_velocity": telemetry.get("leg_velocity"),
                "max_motor_temperature": telemetry.get("max_motor_temperature"),
                "last_error": self.last_error,
                "motion_command_ttl_ms": int(
                    self.MOTION_COMMAND_TTL_SECONDS * 1000
                ),
                "watchdog_ms": int(self.CONTROLLER_TIMEOUT_SECONDS * 1000),
                "watchdog_action": "zero_velocity_keep_mode",
            }

    def close(self) -> None:
        self.stop_event.set()
        with self.lock:
            self.estopped = True
            self.estop_reason = "shutdown"
            self._safe_stop(damping=True)
            self.adapter.disconnect()
            self._release_controller()


class RobotDogServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        service: ControlService,
        pin: str,
    ) -> None:
        self.service = service
        self.pin = pin
        self.session_token = secrets.token_urlsafe(32)
        super().__init__(address, RequestHandler)


class RequestHandler(BaseHTTPRequestHandler):
    server: RobotDogServer

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def _json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 16_384:
            raise ValueError("请求体过大")
        raw = self.rfile.read(length) if length else b"{}"
        body = json.loads(raw.decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("请求必须是 JSON 对象")
        return body

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if getattr(self, "_issue_session_cookie", False):
            self.send_header(
                "Set-Cookie",
                f"robotdog_session={self.server.session_token}; Path=/; HttpOnly; SameSite=Strict",
            )
            self._issue_session_cookie = False
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        supplied_pin = self.headers.get("X-Control-Pin", "")
        if secrets.compare_digest(supplied_pin, self.server.pin):
            self._issue_session_cookie = True
            return True
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return False
        session = cookie.get("robotdog_session")
        return bool(
            session
            and secrets.compare_digest(session.value, self.server.session_token)
        )

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._send_json({"ok": False, "error": "PIN 不正确"}, HTTPStatus.UNAUTHORIZED)
        return False

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            if not self._require_auth():
                return
            self._send_json({"ok": True, "status": self.server.service.status()})
            return
        if path.startswith("/api/"):
            self._send_json({"ok": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        self._serve_static(path)

    def do_POST(self) -> None:
        if not self._require_auth():
            return
        path = urlparse(self.path).path
        try:
            body = self._json_body()
            client_id = str(body.get("client_id", ""))
            service = self.server.service
            if path == "/api/connect":
                service.connect(client_id)
                result: Any = None
            elif path == "/api/disconnect":
                service.disconnect(client_id)
                result = None
            elif path == "/api/arm":
                service.arm(client_id)
                result = None
            elif path == "/api/estop":
                service.engage_estop()
                result = None
            elif path == "/api/heartbeat":
                service.heartbeat(client_id)
                result = None
            elif path == "/api/velocity":
                result = asdict(
                    service.set_velocity(
                        client_id,
                        float(body.get("x", 0.0)),
                        float(body.get("y", 0.0)),
                        float(body.get("yaw", 0.0)),
                    )
                )
            elif path == "/api/action":
                service.action(client_id, str(body.get("name", "")), bool(body.get("confirmed")))
                result = None
            elif path == "/api/test/estop":
                service.set_test_estop(bool(body.get("estopped", True)))
                result = None
            else:
                self._send_json({"ok": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json({"ok": True, "result": result, "status": service.status()})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # A browser may time out a slow response; do not turn a closed
            # response socket into a robot fault or try writing a second reply.
            return
        except PermissionError as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.CONFLICT)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.server.service.last_error = str(exc)
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        candidate = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in candidate.parents and candidate != WEB_ROOT.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.is_file():
            candidate = WEB_ROOT / "index.html"
        data = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix in {".html", ".css", ".js"}:
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mymooo Raspberry Pi 局域网控制台")
    parser.add_argument("--host", default="0.0.0.0", help="网页监听地址")
    parser.add_argument("--port", type=int, default=8088, help="网页端口")
    parser.add_argument("--robot-ip", default="10.21.20.1", help="Mymooo RJ45 地址")
    parser.add_argument("--mode", choices=("mock", "bpx"), default="mock", help="仿真或真实机器人")
    parser.add_argument(
        "--pin",
        default=os.environ.get("MYMOOO_PIN") or os.environ.get("ROBOTDOG_PIN"),
        help="控制 PIN；未设置时随机生成",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pin = args.pin or f"{secrets.randbelow(1_000_000):06d}"
    adapter: RobotAdapter
    if args.mode == "bpx":
        adapter = MymoooRobotAdapter(args.robot_ip)
    else:
        adapter = MockRobotAdapter(args.robot_ip)
    service = ControlService(adapter, args.mode, args.robot_ip)
    server = RobotDogServer((args.host, args.port), service, pin)

    def shutdown_handler(_signum: int, _frame: Any) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown_handler)

    print("\nMymooo 控制台")
    print(f"网页地址: http://<Raspberry-Pi-IP>:{args.port}")
    print(f"控制 PIN: {pin}")
    print(f"运行模式: {'真实机器人' if args.mode == 'bpx' else '仿真'}")
    print(f"机器人地址: {args.robot_ip}\n")
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        service.close()
        server.server_close()


if __name__ == "__main__":
    main()
