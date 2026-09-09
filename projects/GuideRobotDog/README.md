# GuideRobotDog · Mymooo 控制端

Unitree L2 独立接入诊断见 [L2 README](docs/L2_README.md)、[最新协议/IMU/退出诊断报告](docs/L2_PHASE2_REPORT.md) 和 [第一阶段历史报告](docs/L2_DEVELOPMENT_REPORT.md)。IMU已恢复，半速设备时钟仍待解决；尚未进入ROS2。诊断脚本不修改机器人网络。

这是运行在 Raspberry Pi 5B 上的纯 Mymooo 机器狗控制项目。浏览器通过 HTTP/JSON 访问 `server.py`，所有运动命令统一经过 `ControlService` 的控制权、安全锁定和命令时限检查，再交给 `MockRobotAdapter` 或 `MymoooRobotAdapter`。

## 最终网络与控制拓扑

```text
                    MaYi-FC
                       │
              ┌────────┴────────┐
              │                 │
         Windows / 手机    Raspberry Pi 5B
                          wlan0 = DHCP
                       SSH / Web :8088
                        Internet / 维护
                                │
                         ControlService
                                │
                     MymoooRobotAdapter
                                │
                      eth0 = 10.21.20.2/24
                                │
                            Ethernet
                                │
                         Mymooo Robot
                          10.21.20.1
```

- `wlan0` 是 Management Plane，由路由器 DHCP 管理，承载 SSH、Web、Internet 和系统维护。
- `eth0` 是 Robot Control Plane，只连接 Mymooo 专网，不配置 gateway、DNS 或默认路由。
- Web 继续绑定 `0.0.0.0:8088`，不绑定可能变化的 DHCP 地址。

## 运行边界

- 用户：`guidedog`
- 部署目录：`/home/guidedog/robotdog-control`
- Web 与 API：`http://<Raspberry-Pi-IP>:8088`
- Mymooo 地址：`10.21.20.1`
- systemd 默认模式：`mock`
- Python：项目内 `.venv/bin/python`

## 安全语义

- 服务启动、断开和关闭时处于安全锁定状态。
- 非零速度命令必须在 300 ms 内刷新，否则发送零速度并锁定为 `motion_command_timeout`。
- 控制权租约为 3 秒；heartbeat 只续租，不能续运动命令时限。
- 速度、动作或遥测异常锁定为 `adapter_error`，显式恢复前拒绝非零运动。
- 浏览器失焦、切到后台或离开页面时主动发送停止命令。
- Web handler 只进入 `ControlService`，不会绕过安全层直接调用硬件适配器。

## PIN 优先级

```text
--pin → MYMOOO_PIN → ROBOTDOG_PIN（兼容）→ 随机六位 PIN
```

正式部署优先在 `/etc/robotdog-web.env` 设置 `MYMOOO_PIN`。旧的 `ROBOTDOG_PIN` 继续有效。

## 本机 Mock 验证

```powershell
python server.py --mode mock --host 127.0.0.1 --port 8088 --pin 000000
```

打开 `http://127.0.0.1:8088`。该模式不会连接真实机器狗。

## 树莓派部署

完整流程见 [RASPBERRY_PI5_DEPLOY.md](RASPBERRY_PI5_DEPLOY.md)。上传后先保持 mock：

```bash
cd /home/guidedog/robotdog-control
bash scripts/setup-pi.sh
bash scripts/deploy-pi.sh
sudo install -m 0600 etc/robotdog-web.env.example /etc/robotdog-web.env
sudoedit /etc/robotdog-web.env
bash scripts/deploy-pi.sh --start
```

## 管理链路检查

`scripts/check-management-link.sh` 只读取状态，不修改网络：

```bash
bash scripts/check-management-link.sh
```

只有实际验证 Wi-Fi SSH 与 Wi-Fi Web 后，才可以脱离临时 Windows–Pi Ethernet。只有脱离后再次验证成功，才可以人工运行有线专网配置脚本。

## F710 手柄遥控

接收器插入树莓派后，使用 `gamepad.py` 本地读取手柄，通过现有 HTTP API 接入
ControlService。安装、输入检查与按键说明见 [F710 使用说明](docs/F710.md)。
默认只检查输入；显式添加 `--control` 才发送控制请求。

## 未来输入边界

```text
Web Input ───────────┐
Future Gamepad Input ├─> Future Control Arbiter -> Safety
Future Autonomous ──┘                            │
                                                ▼
                                      MymoooRobotAdapter
                                                │
                                             bpx_sdk
```

F710 已通过现有控制权租约接入；自主巡航、避障、跟随或完整 Control Arbiter 尚未实现。

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
node --test tests/test_*.cjs
bash -n scripts/*.sh
```

采购清单不被程序读取。旧迁移资料位于 `docs/history/`，只用于追溯，不代表当前系统组成。
