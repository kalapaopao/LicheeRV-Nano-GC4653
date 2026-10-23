# 80 FPS 主线复现与停机（唯一推荐入口）

> **当前有效版本：** `test/clock36_live_20261023` · SG2002 + GC4653 · Linux `5.10.4-tag-` · 1280×720 · CAM1 分频33 · 约80 FPS。实验只在匹配该板驱动、原寄存器与SDK环境时才可执行。
>
> 旧60/70/72/82 FPS的实验运行方法已迁移到只读 Git 历史，由 [历代研究总结](history/EXPERIMENT_DECISIONS.md) 和 [退役脚本清单](history/RETIRED_LAUNCHERS.md) 检索；不是当前开箱即用方式。

## 1. 运行前需要

1. 确认只有当前一块GC4653摄像头，板端未被其它VI/ISP测试进程占用。
2. 确认板端当前 `uname -r` 为 `5.10.4-tag-`，寄存器 `0x030028c4` 初值为 `0x00200001`，否则**拒绝修改**。
3. SoC温度应低于70°C，摄像头管理锁不存在，板端USB NCM地址例 `10.133.124.1`。
4. 保留原驱动 `soph_mipi_rx.ko`、完整 `/code/camera/lib` 与匹配SDK，不覆盖系统内核和旧冻结基线。

PowerShell只读检查：

```powershell
ssh root@10.133.124.1 'uname -r; cat /sys/class/thermal/thermal_zone0/temp; devmem 0x030028c4 32; ls -ld /code/camera/run/lock 2>&1'
```

## 2. 源代码和编译

唯一本地主线源码：

- [camera_36long.cpp](../test/clock36_live_20261023/camera_36long.cpp)
- [build_long.sh](../test/clock36_live_20261023/build_long.sh)
- [live_36_supervisor.sh](../test/clock36_live_20261023/live_36_supervisor.sh)
- [完整交接与研究边界](../test/clock36_live_20261023/README.md)

在**已经安装匹配的外部Sipeed SDK/编译器**的研究机WSL中：

```bash
bash /mnt/d/study/LicheeRV/test/clock36_live_20261023/build_long.sh
```

现在的 `build_long.sh` 会从 `speed-fry/workspace/camera/src/` 和SDK源文件**重新生成** `common_*.o`、GC4653 sensor对象，不再依赖旧 `speed-fry/build-preview-hd.sh` 或旧 `.o`。项目路径以脚本自身所在checkout推算，生成文件限制在项目根下。

此脚本在本机 WSL 已编译成功，但**新编译的RISC-V二进制本身未做与冻结二进制等量的5分钟实板测试**。历史实板已验证二进制 SHA-256：

`a959fe08f85165fa689db3c6f6d62f5778ba01af41ea3435e46a79637e6ac4bc`

因此，若要复现历史数据，应优先使用与之SHA一致的本地冻结二进制；新编译产物需另做板端验收。

## 3. 部署到板端（不覆盖原程序）

在Windows PowerShell（确保相机空闲）：

```powershell
ssh root@10.133.124.1 'mkdir -p /tmp/clock36_live_20261023'
scp 'D:\study\LicheeRV\test\clock36_live_20261023\camera_36long' root@10.133.124.1:/tmp/clock36_live_20261023/
scp 'D:\study\LicheeRV\test\clock36_live_20261023\live_36_supervisor.sh' root@10.133.124.1:/tmp/clock36_live_20261023/
ssh root@10.133.124.1 'chmod 755 /tmp/clock36_live_20261023/camera_36long; sha256sum /tmp/clock36_live_20261023/camera_36long'
```

直接在板端执行当前唯一推荐启动程序：

```sh
sh /tmp/clock36_live_20261023/live_36_supervisor.sh
```

请确保文件为LF换行；Windows复制的CRLF脚本要先转换。建议前台启动，终端会实时显示日志。管理程序先采集37.125MHz基线样本，随后临时把CAM1分频改为33，开始约36MHz的80FPS实验；带锁、MIPI检查、温度74.5°C上限、300秒自动停机与回退。

## 4. 画面在哪里

程序运行期间，电脑已连板端USB NCM时：

- 页面：`http://10.133.124.1:8081/`
- MJPEG：`http://10.133.124.1:8081/live.mjpg`
- JPEG抓拍：`http://10.133.124.1:8081/snapshot.jpg`

该程序基于单客户端TCP HTTP串行服务，浏览器MJPEG、抓拍多连接可能存在互斥与阻塞。实测板端硬件VI约80、JPEG编码约80、可向已连接客户端发送接近80，但**不能声称浏览器渲染80帧**。60Hz屏幕通常不可能逐次显示全部80帧，且JPEG Q85是有损编码。

## 5. 正常退出与回滚

- 运行中前台按 `Ctrl+C`；不要使用 `kill -9`，也不要强行删除锁。
- 默认满300秒后正常停止并恢复原寄存器，或者温度过高/MIPI新增错误时提前终止。
- 板端停机后手动确认：

```sh
devmem 0x030028c4 32
cat /sys/kernel/debug/clk/clk_cam1/clk_rate
test ! -d /code/camera/run/lock && echo CAMERA_UNLOCKED
```

期望 `0x00200001`、debugfs `37125000`、锁空闲。传感器的真实MCLK物理频率未测，debugfs仍报老时钟率，这套使用 `devmem` 临时分频的方法仅是研究验证，**不适合长期无人值守运行**。

## 6. 历史失败方案在哪里

- [完整阶段成果/失败技术决策](history/EXPERIMENT_DECISIONS.md)
- [所有被删历史调用脚本的SHA与 Git 固定历史链接](history/RETIRED_LAUNCHERS.md)
- [5分钟80 FPS报告、RAW抽检、真实数据](../test/clock36_live_20261023/LIVE_5MIN_RESULTS.md)
- [公开与本地数据边界](PUBLICATION_SCOPE.md)

旧 C++、实验JSON、报告原文件继续留在仓库对应目录，历史脚本从主分支删除但保留Git快照。
