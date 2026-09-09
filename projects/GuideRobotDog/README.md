# GuideRobotDog · Mymooo 控制端

当前阶段：**Phase A — Architecture Baseline + L2 Serial Migration**。
Web 与 F710 已有；L2 正迁移到 **TTL UART → Unitree UART→USB Adapter → Pi USB**。
Serial 实机枚举、SDK、点云、IMU、时间戳、退出及重连均为 **NOT RUN**，尚未进入 ROS2。
见 [Serial 接入与验收](docs/L2_README.md)、[最终架构基线](docs/FINAL_ARCHITECTURE.md)
和 [Phase A 审查记录](docs/PHASE_A_REPORT.md)。
此前 IMU 恢复与约半速时钟是 [Ethernet 历史实测](docs/L2_PHASE2_REPORT.md)，
不代表 Serial 结果；历史报告保留。

这是运行在 Raspberry Pi 5B 上的纯 Mymooo 机器狗控制项目。浏览器通过 HTTP/JSON 访问 `server.py`，所有运动命令统一经过 `ControlService` 的控制权、安全锁定和命令时限检查，再交给 `MockRobotAdapter` 或 `MymoooRobotAdapter`。

## 现有网络与控制拓扑

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
- L2 最终使用 USB 串口，不规划第二张雷达网卡。`/dev/unitree_l2` 是未验证的持久命名目标。
- F710 接收器使用 USB；相机及独立动力断电安全控制器留待后续阶段。

## 运行边界

- 用户：`guidedog`
- 部署目录：`/home/guidedog/robotdog-control`
- Web 与 API：`http://<Raspberry-Pi-IP>:8088`
- Mymooo 地址：`10.21.20.1`
- systemd 默认模式：`mock`
- Python：项目内 `.venv/bin/python`

## 安全语义

以下是现有控制保护。最终设计将 OperatingMode 与 SafetyState 分离，并区分
SOFT_ESTOP（停运动、请求阻尼并锁定，计算系统继续运行）和 HARD_ESTOP（硬件切断动力）。
当前 F710 B 对应软件急停；真实硬断电尚未实现，不能用零速度冒充。
未来默认 UnavailablePowerCutBackend 必须返回 `hardware_power_cut_unavailable`。
完整状态机、独立 RESET/ARM 流程及 Web/F710 硬急停操作均未在 Phase A 实现。

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
Web / F710 → Future Mode Manager → Manual / Follow / Navigation
                                           │
                            Future Control Arbiter → Safety Supervisor
                                                           │
                                                Robot Driver → bpx_sdk
```

F710 已通过现有控制权租约接入。目标模式为 STANDBY、MANUAL_GAMEPAD、MANUAL_WEB、
FOLLOW、NAVIGATION、PATROL、RETURN_HOME；避障是自主模式共用能力。
完整 Mode Manager / Control Arbiter / SafetyState 与自主功能均留待后续，
Phase A 提交后等待 ChatGPT 审查，不自动进入下一阶段。

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
node --test tests/test_*.cjs
for script in scripts/*.sh; do bash -n "$script" || exit; done
```

采购清单不被程序读取。旧迁移资料位于 `docs/history/`，只用于追溯，不代表当前系统组成。
