# 80 FPS / 分频33 实验：代码入口与复现清单

本文件是本项目 **2026-10-23 已实际跑过的 300 秒实时采集**的源码索引与操作交接，实验结果另见 [LIVE_5MIN_RESULTS.md](LIVE_5MIN_RESULTS.md)。

> **研究状态：** LicheeRV Nano SG2002 + GC4653；1280×720；CAM1 的源时钟分频由 32 临时改成 33，按 1,187,999,988 Hz 父时钟推算输出约 36 MHz；实际 VI 帧率约 80 FPS。还未用示波器验证 GC4653 的 MCLK 引脚；这是实验性程序，不是经完整验证的正式驱动。

## 1. 真实实测成绩

| 指标 | 2026-10-23 记录 |
|---|---:|
| 监控运行时间 | 300 秒，计时结束正常停止 |
| 最终累计取帧 | 24,222 帧 |
| 累计 VI / PTS 帧率 | **80.0098 / 80.0099 FPS** |
| 稳定期 59 个5秒窗口平均 VI | **79.98636 FPS** |
| 重复 PTS / 取帧超时 / 编码错误 | **0 / 0 / 0** |
| MIPI ECC / CRC / Header / WordCount / FIFO | **97次巡检未出现错误** |
| 最高观测 SoC 温度 | **72.414°C** |
| 正常结束 | 分频寄存器恢复 0x00200001，独占锁释放 |

证据：[原始统计 JSON](LIVE_5MIN_SUMMARY.json) · [5秒窗口 CSV](LIVE_5MIN_WINDOWS.csv) · [曲线图](../../docs/images/36mhz-live-5min-fps.svg) · [实验报告](LIVE_5MIN_RESULTS.md)。

## 2. 研究代码清单

| 文件 | 用途 |
|---|---|
| [camera_36long.cpp](camera_36long.cpp) | 本次真正运行的 RISC-V C++ 摄像头程序：GC4653 初始化、VI/PTS 采集、VENC JPEG 编码、HTTP MJPEG 服务、分阶段 Bayer 样本 |
| [live_36_supervisor.sh](live_36_supervisor.sh) | 本次真正运行的 Shell 管理程序：启动、独占锁、写 CAM1 分频、温度/MIPI巡检、300秒上限、自动回退 |
| [build_long.sh](build_long.sh) | 本次已验证的交叉编译命令（依赖外部 SDK 与本地先前编译好的公共对象） |
| [summarize_live_5min.py](summarize_live_5min.py) | 从本地未删减日志计算统计 JSON、CSV 和帧率 SVG 的只读分析脚本 |
| [analyze_raw.py](analyze_raw.py) | 将 CVI 导出的压缩关闭后的 Bayer 12bit packed 样本展开、计算顶部行差异 |
| [camera_36probe.cpp](camera_36probe.cpp) | 早期短时 A/B 程序，不是5分钟程序 |
| [run_board_long.sh](run_board_long.sh) | 曾准备的单轮长测草稿，**不是本次实测使用的脚本** |

以上源码和统计已推送 GitHub。实际交叉编译得到的 RISC-V 二进制是**本地保留的构建产物**，不作为源码上传：

```text
camera_36long (riscv64 ELF)
SHA-256: a959fe08f85165fa689db3c6f6d62f5778ba01af41ea3435e46a79637e6ac4bc
```

实机部署时已核对板端 /tmp 下程序的 SHA-256 与本地编译文件一致。

## 3. 构建前提（重要）

`build_long.sh` **不是独立、可从空机器直接编译的脚本**。它使用：

- **Windows 项目根目录：** `D:\study\LicheeRV`（只允许在这里写入项目文件）。
- **WSL Ubuntu 22.04** 和项目冻结的 Sipeed RISC-V musl 交叉编译器。
- 外部/本地 SDK：`speed-fry/workspace/LicheeRV-Nano-Build/`。
- 先前保存的 `speed-fry/build-preview-hd/*.o`（`common_vi.o`、`common_isp.o`、`common_sys.o` 等）。
- 与板端匹配的 CVITEK MMF/ISP/VENC 链接库和传感器代码。

这些大型 SDK、工具链、`.o` 文件因为体积、上游授权与平台匹配问题，被 `.gitignore` 排除，没有上传到 Public GitHub。**只克隆此仓库并不能复现可执行文件；必须另外恢复匹配的 SDK 与公共对象。** 仓库保留了 [历史公共对象构建脚本](../../speed-fry/build-preview-hd.sh)，但其本地环境依赖和相容性需要重新检查。

现有研究电脑、依赖已就绪时，执行（WSL shell）：

```bash
bash /mnt/d/study/LicheeRV/test/clock36_live_20261023/build_long.sh
```

输出保存在当前项目下 `test/clock36_live_20261023/camera_36long`。

## 4. 板端临时部署（研究用途）

板端系统/内核必须与此前一致（实测为 `5.10.4-tag-`）。以下设备 IP 是实验网络环境，不适用于所有用户。**只在有现场操作人员、已验证硬件寄存器和具备回退路径的设备上使用。**

在 Windows PowerShell，先确认摄像头没有被其他程序占用：

```powershell
ssh root@10.133.124.1 "uname -r; cat /sys/class/thermal/thermal_zone0/temp; devmem 0x030028c4 32; ls -ld /code/camera/run/lock"
```

首次启动需确认原寄存器确为 `0x00200001`、设备无摄像头进程/锁、SoC 温度低于 70°C。拷贝本次冻结实验程序到板端 `/tmp`，**不覆盖 `/code/camera/bin`**：

```powershell
ssh root@10.133.124.1 "mkdir -p /tmp/clock36_live_20261023"
scp "D:\study\LicheeRV\test\clock36_live_20261023\camera_36long" root@10.133.124.1:/tmp/clock36_live_20261023/
scp "D:\study\LicheeRV\test\clock36_live_20261023\live_36_supervisor.sh" root@10.133.124.1:/tmp/clock36_live_20261023/
ssh root@10.133.124.1 "chmod 755 /tmp/clock36_live_20261023/camera_36long"
```

请先检查传输后的 SHA-256，确保与上面的冻结二进制一致。Shell 文件要使用 Linux LF 换行。板端启动核心命令（可直接前台查看日志和手动 Ctrl+C；原先的5分钟测试是放到后台日志运行）：

```sh
sh /tmp/clock36_live_20261023/live_36_supervisor.sh
```

它会先用历史 80 档初始化传感器，在取得基线 RAW 后临时修改时钟分频，启动 8081 网页，执行最长 300 秒监测。客户端地址：

- `http://10.133.124.1:8081/`（网页）
- `http://10.133.124.1:8081/live.mjpg`（MJPEG）
- `http://10.133.124.1:8081/snapshot.jpg`（单张抓拍）

程序只支持单客户端连续 MJPEG 连接，其他浏览器连接可能因占用而等待。**不要在同一摄像头被其他采集程序使用时启动**。

### 退出与恢复

管理脚本有 300 秒定时终止、温度阈值 74.5°C、MIPI 错误增加即终止、SIGINT/SIGTERM 清理、原分频值恢复和独占锁清理；另附临时 MMIO 硬件回退任务。**这些是安全措施而非绝对可靠的硬件故障恢复保证**。

调试者应当使用前台的 `Ctrl+C`，或者向管理进程发送 `SIGTERM` 请求正常清理，而不是先用 `kill -9` 或删除锁目录。停机后人工验证：

```sh
devmem 0x030028c4 32
cat /sys/kernel/debug/clk/clk_cam1/clk_rate
test ! -d /code/camera/run/lock && echo CAMERA_UNLOCKED
```

期望回到 `0x00200001`；debugfs 会报 `37125000`。板端旧版系统时钟可能不准确，实验时长以日志 monotonic/程序累计测量为准。

## 5. 关于“80帧无损”的精确定义

- **已验证：** VI/PTS 测得约80FPS、5分钟内采集未报超时/重复PTS、MIPI 97次监测无错误；3次 Bayer 抽样里切分频后顶部亮行显著改善。
- **非无损 JPEG：** 网页中的 JPEG/MJPEG 使用有损压缩；不能称为像素无损视频。
- **非逐帧无条纹证明：** Bayer 导出样本是关闭 VI 压缩的 12-bit packed 格式（每帧 1,382,400 字节），MIPI 数据链路报告 RAW10；不能用少量样本证明每一帧均零花屏。
- **非正式稳定驱动：** Linux CCF 时钟读数与临时 MMIO 修改仍未同步；没有示波器 MCLK 物理测量，也没有10分钟/全温区验证。

**因此当前建议对外表述为：**“GC4653 720P 80FPS，CAM1 约36MHz 分频下五分钟采集零监测错误，Bayer RAW 抽样条纹明显改善；尚待正式驱动与完整画质验收。”
