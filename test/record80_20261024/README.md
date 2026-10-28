# GC4653 80 FPS 采集 + 40 FPS MJPEG AVI 录像（2026-10-24 已上板验证）

## 当前状态：实测跑通

本目录属于真实用户笔记本 `D:\study\LicheeRV` 的实验支线，不覆盖
`test/clock36_live_20261023/camera_36long.cpp`、稳定版二进制或原监督脚本。

复用原版的 **CAM1 分频33（约36 MHz）、720P 80FPS VI/PTS、JPEG Q85 硬件 VENC**。
录像从硬件 JPEG 输出中每隔一帧选择一帧，原生打包 MJPEG AVI，后台线程写入 SD/eMMC。
单帧图像维持 **1280×720、JPEG Q85**，不再通过 FFmpeg 重新压缩。
录像工作时摄像头采集仍约80FPS；AVI 按40FPS播放，本次短测录制均速为38.53FPS。

### 2026-10-24 现场验证报告

| 实际检查 | 实测结果 |
|---|---|
| SSH 与板卡 | 笔记本经 10.133.124.1、10.133.125.1 均成功免密登录，板为 riscv64 |
| 稳定基线 | 旧版 `camera_36long` 的传感器时序/分频监控链路不改动 |
| 首版 80FPS Q85 / FFmpeg 录像 | 2289帧，38.522s，59.42FPS，队列丢帧750；不合格 |
| 第二版 80FPS Q85 / 原生 AVI | 1652帧，27.385s，60.33FPS，队列丢帧424；不合格 |
| 存储写入测试 | 64MiB / 7.60s，约8.4MiB/s；Q85 80FPS 数据量超过写入吞吐 |
| **最终版 80采集 / 40录像** | **951帧，24.682s，录制均速38.53FPS，127.2MiB** |
| **最终版磁盘队列丢帧** | **0** |
| **最终版写入错误** | **0** |
| **FFprobe** | MJPEG，1280×720，AVI 40/1FPS，nb_frames=951 |
| **FFmpeg 解码** | 30帧解码命令退出0，硬件 JPEG 附带的APP字段会产生非致命提示 |
| **网页控制单独实测** | GET 8081 HTTP200；POST 8082/start、/stop 返回accepted，短片自动完成，segments=1，drop=0 |
| 时钟回退 | 每轮退出后 MMIO 恢复 `0x00200001`，`/code/camera/run/lock` 释放 |
| MIPI 监控 | 前两轮监控为0；最后网页测试启动前累计1、运行中未增加 |
| 温度 | 最后一次受监督运行温度最高约72.8°C（预设74.5°C停机） |

注意：**录像写入队列无丢帧不等于硬件采集到录像逐帧全保留**。取流80FPS，JPEG编码线程略有帧替换，录像每两帧保留一帧，故录像真实均速约38.5FPS。
AVI容器标记40FPS，实际采集24.68秒对应951帧，按40FPS播放约23.78秒；有约4%的时间比例差。
用于训练图像无影响，需严格时间同步的训练需补充实际每帧时间戳。
JPEG Q85本来属于有损，不是RAW/像素无损录制。

板端RTC当前错误地显示1970-01-01，因此录像名字为 `gc4653_19700101_*.avi`；原始摄像头采集的FPS统计使用单调时钟，不受此影响。之后应该修复板端RTC/NTP，而不是用文件名推断录像真实时间。

## 使用（以下方式已在板端实际测试）

**已部署实验程序**：

- 板端可执行程序：`/tmp/clock36_record_20261024/camera_36record`
- 板端受监督脚本：`/tmp/clock36_record_20261024/record36_supervisor.sh`
- 板端录像保存：`/code/camera/recordings/*.avi`
- 配套JSON元数据：`*.avi.json`
- 笔记本上的已验证录像：`D:\study\LicheeRV\test\record80_20261024\captures`
- 实验监督/捕获日志：`/tmp/clock36_record_20261024/record_report/capture.log`

板端在空闲、温度小于70°C且寄存器/锁满足监督脚本检查时，单命令启动自动录像（**20~300秒**，到点自动关停、恢复时钟）：

```sh
MAX_RUN_SEC=24 RECORD_TEST_AUTOSTART=1 sh /tmp/clock36_record_20261024/record36_supervisor.sh
```

上面 **24秒参数已实际测试通过**，并产生了951帧的录像。
如果不需要自动开始，则运行：

```sh
MAX_RUN_SEC=24 sh /tmp/clock36_record_20261024/record36_supervisor.sh
```

在监督脚本运行期间，笔记本浏览器可访问 **http://10.133.124.1:8081/** 看实时 MJPEG 预览；页面按钮控制录像。
网页后端API：`http://10.133.124.1:8082/status`、`POST /start`、`POST /stop`；
两种控制请求均已在笔记本实测，停止后AVI成功封装。

录像录完可从板端查看：

```sh
ls -lh /code/camera/recordings/*.avi
```

出于安全性，录像服务仅监听USB网卡上的10.133.124.1。不要把8081/8082端口暴露到公网。
监督脚本还保留最高74.5°C停机、MIPI错误变化停机、300s最长运行、异常后的寄存器回退保护。
因MCLK尚未做示波器实测，该设置仍是实验性约36MHz时钟方案。

**注意 /tmp 在板端重启后可能丢失**。如果程序消失，先用笔记本现有文件重新通过SCP部署（不是旧的desktop/board_record80路径）：

```powershell
ssh root@10.133.125.1 "mkdir -p /tmp/clock36_record_20261024"
scp "D:\study\LicheeRV\test\record80_20261024\camera_36record" "D:\study\LicheeRV\test\record80_20261024\record36_supervisor.sh" root@10.133.125.1:/tmp/clock36_record_20261024/
ssh root@10.133.125.1 "chmod +x /tmp/clock36_record_20261024/camera_36record"
```

## 源码

- `camera_36record.cpp`：沿用当前稳定80FPS VI+VENC，另加录像取样、网页控制API。
- `record80.h`：独立有界队列、后台写盘、原生AVI复用硬件JPEG、AVI索引和元数据。
- `record36_supervisor.sh`：继承实机长测监督、温度、MIPI和分频回退，独立实验路径。
- `build_record.sh`：使用笔记本工程内冻结SDK源码、RISC-V交叉工具链重新编译。
- `test_web_controls.ps1`、`web_control_test.log`：网页/start/stop全流程实测记录。
- `verified_frame.jpg`：从最终录制AVI的10秒处实际解码得到的1280x720抽样截图。
- `captures/*.avi`：从板端SCP拷贝回笔记本的实测录像，SHA256为 `e9f0b2c1f815b261ef90caac553ad0b38c9b77c1b2ce4447f285edd1545751f3`，与板端一致。

两段大量丢帧的失败录像已移动到板端
`/code/camera/recordings/failed_tests_20261024`，不要用于时间连续性训练。未删除，以备交接复盘。

## 尚未宣称完成的工作

- 录像功能的**多段、5分钟以上连续压力测试尚未完成**；
- AVI均匀帧率时间轴与真实采集时刻仍有约4%差异；
- 未做到Q85 1280x720 **全部80FPS录像**（磁盘吞吐不足）；以后可考虑更高速的存储介质，或在板端单独试验H.264/H.265硬件录像与多通道资源限制；
- 未实测录像+目标检测推理同时运行。YOLO数据标注/训练属于下一阶段。
