# Unitree L2 基础接入与诊断

当前状态：**IMU已恢复，点云运行和安全退出wrapper通过；设备时间仍约半速，暂不进入ROS2**。SDK原生关闭仍有已知缺陷。两个扩展坞链路仍未验证。最新结论见`L2_PHASE2_REPORT.md`。

实际运行主机：Raspberry Pi 5 Model B Rev 1.1，Ubuntu 24.04.4 LTS，aarch64。
Pi 上使用独立的 `$HOME/l2_integration` 诊断目录，不操作机器狗控制部署目录。

## 重复运行诊断

```bash
ssh <pi-user>@<management-address>
cd ~/l2_integration
sudo -v
bash scripts/l2_diagnostics.sh > reports/diagnostics-$(date +%Y%m%d-%H%M%S).txt 2>&1
```

接口/IP 未确认时退出码 3 是刻意阻止测试，不能解释为通过。诊断脚本不安装软件、不更改网络、不自动选网卡。
`config/l2.yaml` 是统一配置记录；当前诊断脚本通过命令参数或环境变量取值，不自动解析 YAML。
当前配置记录的是经MAC/插拔和ARP确认的板载`eth0`、L2 `192.168.1.62`、临时主机`192.168.1.2/24`。`network.verified: true`只代表IP/link，`lidar.acceptance_passed: false`仍明确禁止当成完整通过。

确认 L2 网卡 MAC、sysfs USB 路径、插拔对应关系、真实 L2 IP 后：

```bash
read -r -p '已确认的 L2 接口: ' L2_INTERFACE
read -r -p '已确认的 L2 IPv4: ' L2_IP
export L2_INTERFACE L2_IP
sudo -v
L2_CAPTURE_SECONDS=10 bash scripts/l2_network_test.sh
```

快速脚本检查 carrier、直连路由、绑定接口的 ping、邻居表及入站 UDP。抓包禁用混杂模式，不存储负载；临时文本在结束时删除。
退出码：2 参数错误；3 链路/直连路由前提未满足；4 工具/权限/抓包错误；5 未观察到 UDP。
退出 0 仅表示观察到 UDP，不证明点云、IMU或稳定性通过。输出抓包计数、平均包速率、观察到的最大相邻包间隔和每秒计数；tcpdump 内核丢包输出也保留。

## 分层验证顺序

1. 物理接线与供电：先确认一个 USB 网卡能枚举，再逐个加入扩展坞复测；`lsusb -t` 中同一扩展坞可能同时出现 USB2/USB3 Hub，不按条目数推断物理数量。
2. 用 `ip link`、`readlink -f /sys/class/net/接口/device`、`ethtool -i 接口`、MAC 与插拔记录确认接口；`ethtool 接口` 确认协商速率和双工。
3. 先被动观察专用接口的 ARP/UDP，例如 `sudo timeout -s INT 15 tcpdump -p -ni "$L2_INTERFACE" -e 'arp or udp'`。没有目标接口时禁止在 Wi-Fi 上扫描候选雷达网段。
4. 本次在确认ARP目标、路由和SSH经Wi-Fi后，已执行 `sudo ip addr add 192.168.1.2/24 dev eth0`。保留原有`192.168.10.3/24`、`10.21.20.2/24`和Wi-Fi默认路由。重启后临时地址可能消失，复测前重新检查，不能盲目重复add。撤销本次临时地址的精确命令为 `sudo ip addr del 192.168.1.2/24 dev eth0`，不要删除其它地址；当前未撤销以便继续硬件诊断。恢复机器人本体接线前先规划单独USB网卡。
5. 原生 SDK 在独立目录固定官方 tag/commit，先检查示例是否修改工作模式或设备配置，再决定运行方式。不得直接运行会改永久配置的示例。
6. 原生 SDK 点云/IMU连续运行至少60秒，记录帧数、序号缺口、频率、XYZ/Intensity范围、非有限值、原始时间戳与 monotonic 时间。缺失指标标记 unavailable，不能填0伪装通过。
7. 10秒单调时间窗口对照 LiDAR 与 IMU 原始时间戳增量，异常不偷偷修正。
8. 上述通过后再判断实际 ROS2 安装及版本，建立独立 `~/unitree_l2_ws`；未通过之前不安装 ROS2、Point-LIO 或 Nav2。

## 坐标和后续结构

[官方坐标定义](https://github.com/unitreerobotics/unilidar_sdk2#2-coordinate-system-definition)：点云原点为底部安装面中心，+X 背离底部出线方向，+Z 垂直底面向上，+Y 按右手系确定。IMU 与点云轴平行，但原点有偏移，未来 wrapper 必须处理这一差异，不能把不同原点的数据仅改 frame 名当成变换。

`base_link → lidar_link` 安装外参尚未测量。配置使用 null/TODO，`publish_tf: false`，不发布虚假的零外参。
未来 package 划分：`unitree_l2_driver`（C++ SDK→ROS2）、`unitree_l2_bringup`（参数/launch）、`unitree_l2_description`（经测量的TF）、`unitree_l2_processing`（滤波/高度切片/障碍物）。这些 ROS2 package 当前尚未创建。

数据管线保留一个3D源：`/lidar/points → 点云滤波/地面处理/高度切片 → pointcloud_to_laserscan → /scan`；3D SLAM并行消费原始点云和`/lidar/imu`。不依赖L2原生2D模式，不默认启动RViz、不保存所有点云。

原生验证后才能执行 ROS2 验收：`ros2 topic list`、`ros2 topic hz /lidar/points`、`ros2 topic hz /lidar/imu`、`ros2 topic echo /lidar/imu --once`；对照 publisher/subscriber QoS，再用开发电脑 RViz 检查 `Fixed Frame=lidar_link`。

## 已完成的原生编译与复现

第二阶段常规运行请使用安全版本，原`l2_monitor`保留作已知崩溃复现：

```bash
cd ~/l2_integration
bash scripts/build_l2_phase2.sh
./l2_monitor_safe 192.168.1.62 192.168.1.2 65 reports/safe-retest
# SIGINT/SIGTERM均保存CSV和JSON；不足60秒标INCOMPLETE并返回10，不冒充PASS。
# 必须等上一个接收程序完全退出后再启动被动探针：
python3 scripts/l2_wire_analyzer.py --live 65 --output reports/wire-retest
python3 scripts/l2_wire_analyzer.py --pcap reports/phase2/mode0-raw10.pcap --output reports/offline-retest
python3 scripts/l2_sequence_analyzer.py reports/wire-retest-frames.csv reports/sequence-retest.json
bash scripts/test_l2_safe_shutdown.sh
```

`l2_monitor_safe`把官方reader放在子进程内，自己无统计线程；信号只置标志，主循环结束后flush/close自己的文件，再用`_Exit`避开SDK析构。父进程等待、转发信号并记录真实退出码；超时会终止子进程并保留FAIL。返回0只代表点云runtime达到本阶段要求和受控结束，绝不意味着原始设备时钟已修复。
`*-summary.json`与`*-supervisor.json`分别记录runtime与cleanup。原生closeUDP仍为KNOWN_BUG，不应在正式退出路径调用；ASAN只覆盖本项目代码，不能证明预编译库内部安全。

配置已从实测5改到0，执行前获用户明确授权，且只写入一次、重启一次，随后读回0并持续收到IMU。常规诊断不写模式、不校时；`l2_mode_once`、`l2_sync_once`是受控实验工具，不是bringup步骤，不应重复运行。

UDP探针现按header声明的frame长度拆分一个UDP数据报中的多个帧，再校验payload CRC。IMU真实结构80字节，点云1044字节；旧注释156字节不准确。`l2_udp_probe.py`现委托修正后的解析器。序号以真实CSV重新分析，1023→0是观察到的1024周期循环；缺口继续UNKNOWN，不折算成packet loss。

以下为第一阶段历史复现命令与发现，不作为当前默认启动方式：

官方源：[v2.0.10](https://github.com/unitreerobotics/unilidar_sdk2/releases/tag/v2.0.10)，commit `0e3c51f512e6b8ff60b8c32f160b412cb48445c2`，无活动branch（tag archive）。包SHA256 `8313a85e4bc1a47b73f98cccb9c887c41d897d6a71e800e9b5b03cd4f0fc8131`，与用户已有同名zip一致。库运行时报告2.0.9，记录此上游差异。
`L2_SDK`目录是Point-LIO/ROS1工程，本次未修改或编译。

```bash
cd ~/l2_integration
bash scripts/build_l2_monitor.sh
timeout 75 ./l2_monitor 192.168.1.62 192.168.1.2 65 reports/retest > reports/retest.log 2>&1
echo "$?" > reports/retest-exit.txt
python3 scripts/check_l2_acceptance.py reports/retest-summary.json reports/retest-exit.txt
# 上一程序结束且6201端口释放之后，单独验证原始UDP，绝不与SDK同时绑定：
python3 scripts/l2_udp_probe.py 192.168.1.2 192.168.1.62 12 reports/passive-retest
```

监测程序调用官方库initializeUDP（18圈/帧，use_system_timestamp=false），只发送版本/配置读取请求，不发送设置模式、启动/停止、重启、地址修改或显式校时指令。SDK内部行为不等同于纯被动接收，所以另用不发送任何报文的UDP探针独立复核时间。
每帧CSV保留点数/范围/原始时间戳/monotonic；每10秒打印时间增量；仅保存第20帧真实XYZ快照供复查。没有持续保存全部点云。
`sequence_gaps`是按连续uint32序号假设统计的缺口，`sequence_resets`独立记录回退；在序号语义/设备回退未查清前，**不能直接命名为真实丢帧数**。SDK packet_errors为null，不是假零。

已复现`closeUDP()`导致退出139。程序先flush实测报告再关闭，使失败也有证据；这不意味着崩溃已修复。验收还必须检查程序退出码，不能只看JSON。第一轮关闭前未flush造成空summary，该次失败日志被保留；第二轮单独记录，不覆盖原始失败。
CRC诊断按实测payload区间`[12:-12]`计算，原先按header+payload计算会全报不匹配，已修正并重新实测；不能把旧算法结果当成链路损坏证据。

相似现象的上游问题：[设备时间半速 #25](https://github.com/unitreerobotics/unilidar_sdk2/issues/25)、[ARM64 closeUDP崩溃 #18](https://github.com/unitreerobotics/unilidar_sdk2/issues/18)。它们是旁证，不能代替本机证据；未擅自刷固件或修改时间比例。
