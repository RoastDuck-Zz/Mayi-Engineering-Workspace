# Unitree L2 第二阶段实机结论

测试日期：2026-09-09。本文只保留适合进入 Git 的结论；原始 PCAP、CSV、日志、MAC 和管理网地址保留在本地，不上传。

## 1. Actual work_mode

只读响应实测 `work_mode=5`，其中 bit 2 禁用 IMU。经明确授权，只执行一次 `setLidarWorkMode(0)` 和一次软重启，随后读回 0。

## 2. IMU protocol

一个 UDP datagram 可包含多个协议帧，解析器按 header 声明长度拆分。实测 IMU 为 type 104、80 字节，点云为 type 102、1044 字节，均进入主机 UDP 6201。

## 3. IMU root cause

模式 5 下没有 IMU；唯一配置改变为模式 0 后，IMU 持续恢复。因此本机 IMU 缺失的直接原因是工作模式禁用。

## 4. Raw distribution

模式 0 下无 SDK 控制命令被动接收 65 秒：21,611 个 UDP datagram、16,237 个 IMU 帧、5,685 个点云帧，CRC 错误 0。

## 5. Sequence semantics

两个数据流均观察到精确 `1023 -> 0`。按实测记为 1024 周期循环；其它不连续不能证明网络丢包，`confirmed_packet_loss=UNKNOWN`。

## 6. Timestamp format

DataInfo 使用 uint32 秒和 uint32 纳秒。纳秒字段范围有效，点云与 IMU 均未观察到设备时间回退。

## 7. Half-rate root cause

纯 UDP 和官方 SDK 路径都测得约 0.5 的时间增速；自有解析没有比例换算。问题定位到设备/固件输出层，具体固件计时机制没有源码证据，保持 UNKNOWN。

## 8. Sync experiment

获授权后只执行一次 `syncLidarTimeStamp`。校时前 35 秒：IMU 比值均值 0.499468，点云 0.499470。校时后：IMU 0.499654，点云 0.499653。命令把 epoch 起点拉近系统时间，但偏差随后继续增长，因此没有修复半速。

## 9. gdb

最小复现只有一个线程。崩溃发生在 `UDPHandler` deleting destructor；D0 调用 D2，D2 又跳回 D0，形成递归直到栈耗尽。

## 10. Shutdown

`l2_monitor_safe` 把 SDK reader 放在子进程中，先刷新本项目统计，再用 `_Exit` 避开 vendor 析构；父进程转发 SIGINT/SIGTERM、回收子进程并保留真实退出码。SIGINT、SIGTERM 和强制子进程失败传播测试通过。

## 11. Firmware findings

硬件 2.2.1.1，固件 2.8.11.1。未刷固件，未修改 IP/MAC 或永久网络配置。

## 12. SDK findings

官方 tag v2.0.10、commit `0e3c51f512e6b8ff60b8c32f160b412cb48445c2`；运行库自报 2.0.9。ARM64 `closeUDP()` 缺陷仍存在。

## 13. Device findings

安全监测 65 秒收到 309 帧聚合点云和 16,233 条 IMU，非有限点 0、非有限 IMU 0，最大点云间隔 0.233 秒。点云范围和强度均为真实非零数据。

## 14. UNKNOWN

非相邻序号变化是否代表丢包、半速时钟的固件内部机制、模式设置是否跨断电永久保存，以及两个扩展坞端到端性能仍为 UNKNOWN。

## 15. Revised acceptance

```text
POINT CLOUD RUNTIME PASS
IMU PASS
TIMESTAMP FAIL
SDK CLEANUP KNOWN BUG
READY FOR ROS2 NO
```

当前停止在设备时间戳层，不进入 ROS2、Point-LIO、Nav2 或人体跟随。
