# Raspberry Pi 5B / Mymooo 部署指南

这是可公开的部署契约。管理地址由操作者从当前网络确认，本文没有保存私人网络状态。
仓库中的全部软件测试可独立运行，不依赖本地历史部署记录或硬件 SDK。

## 软件检查

在仓库的 `projects/GuideRobotDog` 内，使用 Python 3.11+、Node 22+ 和 Bash：

```bash
python -m unittest discover -s tests -v
node --test tests/test_*.cjs
for script in scripts/*.sh; do bash -n "$script" || exit 1; done
```

Windows 使用 Git Bash；Python 可设置 `PYTHONUTF8=1` 避免子进程编码差异。
软件测试用 mock/fixture，不连接机器人或雷达。Linux C++ 夹具测试使用系统已有 g++，
不安装官方 SDK。无编译器时该组明确 skip，不等于 native 验证通过。

## 操作者部署

先确认 Wi-Fi SSH 管理通道和当前 Pi 地址。将项目部署到
`/home/guidedog/robotdog-control`，运行用户为 `guidedog`。
下列安装/服务命令只供操作者在现场维护窗口执行，CI 和诊断工具不会执行它们：

```bash
cd /home/guidedog/robotdog-control
bash scripts/setup-pi.sh
.venv/bin/python -m unittest discover -s tests -v
bash scripts/deploy-pi.sh
```

在 `/etc/robotdog-web.env` 由操作者配置独立控制 PIN，权限设为仅管理员可读，
不要提交该文件。MYMOOO_PIN 优先，ROBOTDOG_PIN 兼容；不沿用公开示例值。
确认 systemd 配置仍为 `--mode mock` 后，再由操作者执行
`bash scripts/deploy-pi.sh --start`。在 `http://<confirmed-pi-address>:8088`
验收 Web；启动服务不是实机运动安全验收。

## 硬件与维护边界

- wlan0：Wi-Fi 管理通道，承载 Web 与 SSH；不固定私人地址。
- eth0：机器人专网，目标 Pi 10.21.20.2/24、机器人 10.21.20.1；无默认网关/DNS。
- L2：TTL UART → Unitree UART→USB Adapter → Pi USB；目标 `/dev/unitree_l2`
  在 B2 已为当前适配器安装私有持久命名规则。操作步骤见 [L2 README](L2_README.md)。
- F710：USB 接收器，经本机 HTTP 进入现有控制服务；见 [F710](F710.md)。

网络配置脚本会改变系统状态，不能在部署时自动执行。先使用
`bash scripts/check-management-link.sh` 只读检查并在现场确认 Wi-Fi SSH/Web，
再单独安排需要的网络维护；不要在当前控制链路上盲目改网或拔线。
服务重启也可能停止旧连接，必须由操作者安排。本指南不指示启动真实运动模式。

SOFT_ESTOP 与未来硬件 HARD_ESTOP 的区别、尚未实现的模式管理及自主能力见
[最终架构基线](FINAL_ARCHITECTURE.md)。当前没有经过验收的动力断电链路；
不要把零速度或进程退出当成 HARD_ESTOP。

## L2 私有持久设备规则

正式 `udev/99-unitree-l2.rules` 包含本机 USB 序列号，只保留在 Pi，
已通过 udev/.gitignore 排除提交。换机不能直接套用这个规则：先运行
`bash scripts/l2_serial_discover.sh`，以操作者确认的适配器读取同一 USB
父设备的 VID、PID、serial，检查整机只有一个 tty 匹配这一组合。
不得只用 VID/PID。生成本机规则后，先验证匹配唯一性，再执行
`udevadm verify udev/99-unitree-l2.rules`；通过后方可安装到
`/etc/udev/rules.d/99-unitree-l2.rules`、reload rules 并仅 trigger 目标 tty。
检查 `/dev/unitree_l2` 解析结果，最后在停止 monitor 后由操作者实物重插验证。
规则只增加 symlink；不更改用户组、设备模式或网络。当前运行仍需已有串口权限
或显式 sudo。私有规则内容、完整 USB topology 不应上传公开仓库。
