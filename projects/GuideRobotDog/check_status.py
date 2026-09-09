#!/usr/bin/env python3
"""Read-only BPX status client. This module never sends robot commands."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def fetch_status(base_url: str, pin: str, timeout: float = 2.0) -> dict[str, Any]:
    request = Request(
        f"{base_url.rstrip('/')}/api/status",
        headers={"X-Control-Pin": pin},
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not payload.get("ok") or not isinstance(payload.get("status"), dict):
        raise RuntimeError(payload.get("error", "状态接口返回异常"))
    return payload["status"]


def format_status(status: dict[str, Any]) -> str:
    connected = "已连接" if status.get("connected") else "未连接"
    estopped = "急停中" if status.get("estopped") else "已解除"
    controller = status.get("controller_id") if status.get("controller_active") else "空闲"
    battery = status.get("battery")
    temperature = status.get("max_motor_temperature")
    battery_text = "--" if battery is None else f"{battery}%"
    temperature_text = "--" if temperature is None else f"{temperature}°C"
    return "\n".join(
        [
            "=================",
            "BPX状态",
            "=================",
            f"连接: {connected}",
            f"急停: {estopped}",
            f"原因: {status.get('estop_reason', '--')}",
            f"控制权: {controller}",
            f"机器人状态: {status.get('motion_state', '--')}",
            f"电量: {battery_text}",
            f"温度: {temperature_text}",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="安全读取 BPX 控制服务状态")
    parser.add_argument("--url", default="http://127.0.0.1:8088")
    parser.add_argument("--pin", default=os.environ.get("ROBOTDOG_PIN", ""))
    args = parser.parse_args()
    if not args.pin:
        parser.error("请通过 --pin 或 ROBOTDOG_PIN 提供控制 PIN")
    try:
        print(format_status(fetch_status(args.url, args.pin)))
    except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
        print(f"状态读取失败: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
