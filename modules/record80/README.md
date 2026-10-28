# GC4653 录像模块 · record80

**工程入口：** `D:\study\LicheeRV\modules\record80`

独立可部署的 **LicheeRV Nano (SG2002) + GC4653** 录像功能：复用 2026-10-23 验证的 CAM1 ÷33、约 36 MHz、1280×720 约80FPS采集及 JPEG Q85 硬件编码链路；录像从已经编码好的 JPEG 中每两帧取一帧，原生写 **MJPEG AVI（标称40FPS）**，不通过 FFmpeg 再编码。单帧仍是1280×720 Q85，录像使用独立写盘线程。

**已验证：** 原实验录制951帧 / 24.682秒、38.53FPS，队列0丢帧；模块化后在正式持久路径又实际录制**961帧 / 24.767秒、38.802FPS**，队列0丢帧、写入错误0，FFprobe识别961帧。网页启动/停止录制另有49帧测试（录制5.027秒、0队列丢帧）。**未验证：** 连续多小时/多段压力测试、全部80FPS原画幅录像、全帧无条纹、与YOLO同步推理。详见 [实测报告](docs/TEST_REPORT.md)。

> ⚠️ 原工程此前约80FPS的实测属于摄像头VI/PTS取流，并非80FPS录像。当前板端写盘约8.4MiB/s，无法维持全80FPS的Q85 MJPEG。硬件分频33未用示波器确认MCLK实体引脚，仍为受监督的研究配置。

## 目录

| 文件/目录 | 作用 |
|---|---|
| `src/camera_36record.cpp` | 摄像头取流、已验证的JPEG VENC、HTTP预览、录像控制接口 |
| `src/record80.h` | MJPEG AVI封装、后台写盘、有界队列、分段、录像统计 |
| `scripts/build.sh` | WSL RISC-V交叉编译（引用项目内speed-fry配套SDK） |
| `scripts/deploy.ps1` | 从**本笔记本**部署到板端持久目录并核对SHA-256 |
| `scripts/run_board.sh` | 板端温度/MIPI/时钟/摄像头互斥保护与自动恢复 |
| `config/record80.yaml` | 唯一运行参数入口；启动前校验，修改后需重启 |
| `scripts/sync_recordings.ps1` | 下载录像与元数据到本模块 `captures/` |
| `scripts/extract_frames.ps1` | 将录像抽帧至本模块 `dataset_frames/` 供YOLO标注 |
| `bin/camera_36record` | 本机已构建的 riscv64 ELF（二进制，非源码） |
| `docs/USER_GUIDE.md` | **使用与故障排查** |
| `docs/HANDOFF.md` | **开发交接：接口、依赖、限制、验证与回退** |
| `docs/TEST_REPORT.md` | **可复核的实测结果与证据** |

## 最快使用（先部署一次）

**板端操作手册：** [完整说明](docs/BOARD_README.md) 包含 YAML 绝对路径、曝光单位、启动/停止、USB/Wi-Fi预览和故障处理。只更新文档使用 `scripts/sync_board_docs.ps1` 同步根目录及模块 README，不覆盖板端参数；无线示例：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\study\LicheeRV\modules\record80\scripts\sync_board_docs.ps1" -BoardIp 192.168.1.102 -HostKeyAlias 10.133.125.1`。

部署会将 `docs/BOARD_README.md` 同步为板端 `/code/camera/modules/record80/README.md`，其中第一节就是启动命令；已有板端 README 会先备份。旧部署脚本未上传 README，因此本地说明存在并不代表板端已经同步。单独补同步文档时不要为了更新 README 而重部署整个程序，以免覆盖正在板端调整的 YAML。

在**笔记本 Windows PowerShell**：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\study\LicheeRV\modules\record80\scripts\deploy.ps1"
```

在**荔枝派 SSH 终端**（不是Windows）：

```sh
# 先检查 YAML，再按 YAML 启动；默认手动通过网页按钮录像，最多300秒
sh /code/camera/modules/record80/run_board.sh --check-config
sh /code/camera/modules/record80/run_board.sh
```

网页：`http://10.133.124.1:8081/`（仅在运行期间、电脑能访问 USB 网络时有效），录像控制HTTP API在8082端口。
录像默认落板端 `/code/camera/recordings/*.avi`，随片生成 `*.avi.json`；**并不是默认保存到Windows桌面**。
下载回笔记本：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\study\LicheeRV\modules\record80\scripts\sync_recordings.ps1"
```

详见 [《使用手册》](docs/USER_GUIDE.md)、[《交接文档》](docs/HANDOFF.md)、[《测试报告》](docs/TEST_REPORT.md)。
曝光、增益等参数及安全边界见 [《调参说明》](docs/CONFIG.md)。

当前YAML为手动曝光5000us、三种AE增益1倍、BLC四通道256，并保留原自动白平衡。**同一条正式启动命令即可应用，不再需要临时诊断入口。**`--check-config`会显示BLC配置，运行日志的`RECORD80_BLC_VERIFY ... match=1`用于核对实际生效。旧YAML不含BLC字段时保持原ISP行为；改成`black_level_mode: default`可回退。BLC256不是全场景色准保证，其他增益/光源仍需验证。

## 保留与回退

- **稳定80FPS研究原版：** `test/clock36_live_20261023`，完全不修改。
- **已验证录像实验记录：** `test/record80_20261024`（原始跑板测试、AVI、日志、抽帧），作为审计证据保留。
- **持久板端模块：** `/code/camera/modules/record80`；不覆盖 `/code/camera/bin/camera_http80`。
- 停止请优先 `Ctrl+C`，让监督脚本复原时钟到 `0x00200001` 并释放共享锁；不能同时运行两个占用摄像头的程序。
