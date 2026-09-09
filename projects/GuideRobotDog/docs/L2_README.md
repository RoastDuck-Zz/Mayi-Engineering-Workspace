# Unitree L2 Serial 接入与验收

**当前目标：L2 TTL UART → Unitree UART→USB Adapter → Raspberry Pi 5B USB。**
已实现独立 Serial Core v1：串口、组帧、CRC、点云/IMU 解码、时间分析和诊断。
见 [使用说明](L2_SERIAL_CORE.md)与 [最新 B2 验收报告](PHASE_B2_REPORT.md)。
官方自动校时路径不作为 runtime；READY FOR ROS2 = **NO**。
最终拓扑与控制安全边界见 [最终架构](FINAL_ARCHITECTURE.md)。

## Current target Serial deployment

Pi 的 eth0 留给机器狗（10.21.20.1），wlan0 承载 Web/SSH。
L2 不占用 Ethernet，不再以第二张网卡作为最终部署方案。
当前已为操作者确认的适配器安装私有唯一序列号规则，目标名 `/dev/unitree_l2`。
不得把该映射假定为其它机器的事实；不永久依赖 `/dev/ttyACM0`。

`config/l2.yaml` 只记录目标和证据，现有脚本不解析该 YAML，也不会据此自动配置硬件。
`lidar.*_target` 是目标；B2 已实际读回 Serial mode8 并收到原生数据。
但持续 CRC/framing 错误使整体 acceptance 仍为 false。`historical_ethernet` 是过去实测，
不能用于 Serial 自动回退或验收。配置中的禁止写入字段是政策记录，不是已实现的执行保护。

目标 `work_mode=8`：Standard FOV、3D、IMU enabled、Serial、Power-on auto start。
官方固定版本的 [工作模式位定义](https://github.com/unitreerobotics/unilidar_sdk2/blob/0e3c51f512e6b8ff60b8c32f160b412cb48445c2/README.md#32-configuring-work-mode)
规定 bit 3 选择 Serial，其余相关位为 0；Ethernet 对应 0。
此前设备读回 0；本轮获授权后一次 SET8、一次 reset，Serial 已读回8。不要直接运行厂商示例；
固定源码与 x86_64 库已完成本轮审计，见 [SDK 审计](L2_SERIAL_SDK_AUDIT.md)。
`runParse()` 内部会调用校时，`use_system_timestamp=false` 不会关闭它；公开 API
没有禁用开关。独立 Core 已替代该接收路径，源码不链接官方 reader。

普通启动、bringup、driver、diagnostics **不得设置工作模式**，也不得校时、重启或写永久配置。
如果设备模式不符，停止接入验收；未来需经用户明确授权后使用独立一次性工具
本轮一次性工具为 `scripts/l2_transport_mode_once.py`，严格独立于 monitor。
默认只查询；任何后续切换仍需单独授权，不能纳入 service/driver 自动启动。

## 第一步：只读串口发现

由操作者在 Pi 的项目目录执行：

```bash
bash scripts/l2_serial_discover.sh
```

不需要 sudo。工具只列出 `lsusb`、`lsusb -t`、ttyACM/ttyUSB 候选、
`udevadm info` 的属性和父设备属性、`/sys/class/tty/.../device` 解析路径，
以及已有的 `/dev/unitree_l2`、`/dev/serial/by-id`、`/dev/serial/by-path`。
它不打开串口、不读数据流、不改波特率/DTR/RTS、不加载 SDK、不选定设备，
不改 IP/网络/工作模式，不安装软件、不创建/重载 udev 规则，不写输出文件。
缺工具或查询失败会明确报告并继续收集其它信息。

| 返回码 | 仅表示发现工具状态 |
|---|---|
| 0 | 元数据查询完成且存在候选；**不代表 L2 已识别或验收通过** |
| 2 | 非 Linux 或多余参数，未执行 USB 检查 |
| 3 | 查询完成但没有 ttyACM/ttyUSB 候选 |
| 4 | 工具、目录缺失或查询失败，清单不完整（优先于 3） |

测试夹具可设置 `L2_DISCOVERY_DEV_ROOT`、`L2_DISCOVERY_SYS_TTY_ROOT`；
任何非默认目录都输出 OVERRIDDEN，不能作为 Pi 实机证据。正式采集使用默认目录。
Windows 测试只模拟元数据，不模拟点云或 IMU，不证明真实 USB 枚举。

操作者需结合实际适配器接线、设备父路径和经安全安排的插拔对应关系确认身份；
多个候选时不能选择“第一个”。设备访问组/权限也必须实查，工具不自动修改。
原始输出可能包含 USB 序列号和拓扑，应保存在本地，不直接提交公开仓库。

## 持久命名

此前 Phase A 的示例保持不可安装；B2 当前适配器的真实属性已在 Pi 验证，
含序列号的正式规则只保存在 Pi，不提交 Git。部署步骤见 PI_DEPLOYMENT.md。原
[udev 示例](../udev/99-unitree-l2.rules.example)：
**TEMPLATE ONLY / NOT READY TO INSTALL**，所有行都被注释，无可生效规则。
未来用真实、同一 USB 父设备上的属性替换占位符，并验证匹配唯一性。
序列号不存在或不唯一时需基于实际拓扑设计规则，不能猜 VID/PID。
验证重插后稳定指向正确设备才可记录 `device_verified: true`。

## Serial 分层验收顺序

1. USB enumeration：实际 Pi 输出与物理接线对应，记录操作系统、USB 拓扑与适配器身份。
2. Serial identification：确认真实设备节点、权限及持久名称；节点存在不代表 mode=8。
3. Native Serial runtime：官方 SDK 自动校时路径已排除；使用独立 Core，
   检查波特率、帧完整性和错误统计。不开启模式写入、校时或启动旋转命令。
4. Point cloud：验证持续非空帧、有限 XYZ/Intensity、范围、点数、帧率、接收间隔及序号变化。
   未知序号语义不能折算成真实丢包；缺失指标记 unavailable，不填假零。
5. IMU：持续收到有限的加速度、角速度、姿态及原始时间戳；点云通过不代表 IMU 通过。
6. Timestamp：分别记录 LiDAR/IMU 原始秒/纳秒、主机 monotonic 接收时间，做至少一个 10 秒
   窗口，再做 ≥60 秒稳定测试中的连续窗口。每个流计算
   `device_delta_seconds / monotonic_elapsed_seconds`，记录范围、漂移、回退和中断。
   验收前明确误差阈值；历史检查器的 0.98–1.02 仅作为待目标验证的候选范围，不能据此假 PASS。
   不乘 2 修正，不以系统时间戳替代原始时间掩盖比例异常，不自动校时。
7. Clean shutdown：正常结束、SIGINT、SIGTERM 均保留结果及真实退出码，检查串口释放，
   再次启动是否成功；不足时长标 INCOMPLETE。Serial 退出不能沿用 UDP wrapper 的 PASS。
8. USB reconnect：由操作者安全安排断连/重连，验证断流检测、退出/资源回收、正确适配器重新识别；
   不自动修改模式，不恢复任何机器狗运动。持续运行与重连需要独立证据。
9. 上述关键项全部通过并经评审，才进入 ROS2 Driver，随后 Point-LIO 与 Nav2。

| Serial 验收项 | 本阶段状态 |
|---|---|
| SERIAL ENUMERATION | PASS，私有唯一匹配规则及物理重插验证 |
| SERIAL SDK RUNTIME | EXCLUDED |
| NATIVE SERIAL RUNTIME | 10/60 秒均收到真实数据，完整性验收 FAIL |
| POINT CLOUD | OBSERVED，存活点有限；持续 CRC/framing 错误 |
| IMU | OBSERVED，raw values 有限 |
| TIMESTAMP | 两路 raw 增速约0.4996；未校时、未启用倍速修正 |
| STABILITY（≥60 秒） | FAIL：持续 CRC/framing 错误 |
| STREAMING CLEAN SHUTDOWN | PASS：正常结束、SIGINT、SIGTERM、重新打开 |
| USB RECONNECT | PASS：人工重插后别名恢复、重新接收10秒 |
| READY FOR ROS2 | NO |

最新实测见 [B2 报告](PHASE_B2_REPORT.md)；B1 的1byte历史记录保留不改。
本轮获授权后0→8、一次L2 reset，实际数据已恢复但完整性仍未通过。
官方 Serial 程序没有运行。
discovery 仍仅查询元数据，既不加载 SDK 也不打开 tty。

## Previous verified Ethernet bench setup — historical evidence

[L2_PHASE2_REPORT.md](L2_PHASE2_REPORT.md) 原文保留，不修改历史事实。
当时 Raspberry Pi 5B / Ubuntu 24.04.4 / aarch64 经 Ethernet/UDP 实测，
临时雷达/主机端点及端口保存在 `historical_ethernet`，不是当前部署默认值。

- 授权的一次性设置使模式从 5 改为 0，随后读回 0，IMU 恢复。
- 点云与 IMU 有实测数据，但两者时钟增速约为真实时间的 0.5 倍；一次授权校时未修复比例。
- 官方 ARM64 `closeUDP()` 析构有已知崩溃；历史 `l2_monitor_safe` 用进程隔离避开析构，
  这不是 vendor 缺陷修复，更不是 Serial cleanup 的验收结果。
- SDK provenance 为 v2.0.10 / `0e3c51f512e6b8ff60b8c32f160b412cb48445c2`；
  运行库曾自报 2.0.9，上游差异保留。

Ethernet 半速问题在 Serial 上是否仍存在是 UNKNOWN，必须重新测量。
历史 `l2_diagnostics.sh`、`l2_network_test.sh`、UDP probes/analyzers、
`build_l2_monitor.sh`、`build_l2_phase2.sh`、`test_l2_safe_shutdown.sh` 和 `native/l2_*`
保留作追溯，**不是 Serial bringup**。`l2_mode_once` / `l2_sync_once` 不得纳入自动启动。
旧 Ethernet 验收器的序号假设也不能不加审查地用于 Serial。
过去临时网卡/IP 状态不是当前事实；本阶段不撤销或重新配置任何真实网络。

## 后续数据与坐标边界

后续 `Native Serial Core → PointCloud + IMU → 时间验收 → 避障/目标跟踪 → 安全控制`。
ROS2、Point-LIO、Nav2 尚未实现。
主题目标 `/lidar/points`、`/lidar/imu` 尚未发布；ROS2 packages 尚未创建。
`base_link → lidar_link` 外参未测量，配置保持 null、`publish_tf: false`。
点云与 IMU 坐标轴平行但原点不同，未来驱动应遵循
[官方坐标定义](https://github.com/unitreerobotics/unilidar_sdk2/blob/0e3c51f512e6b8ff60b8c32f160b412cb48445c2/README.md#2-coordinate-system-definition)，不能只改 frame 名冒充坐标变换。
未来保留 3D 源供 LIO，并经滤波/地面处理/高度切片形成导航障碍物输入；
不依赖 L2 原生 2D 模式，不默认开启 RViz 或持续保存全部点云。
