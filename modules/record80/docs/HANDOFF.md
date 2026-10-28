# 开发交接文档｜SG2002 GC4653 录像模块

> 后续更新：正式入口已接入YAML可选黑电平字段（`black_level_mode`及R/Gr/Gb/B四通道），当前预设manual256、手动曝光5000us/1倍AE增益。旧YAML省略BLC字段时保留原ISP/PQ行为，启动命令和录像接口不变；设置及内部读回失败会停止。下文模块化基线是原始记录，新增逻辑与验收见[调参说明](CONFIG.md)和[BLC正式集成报告](../../../test/blc_config_20261024/TEST_REPORT.md)。

**模块**：`modules/record80`　**整理时间**：2026-10-24　**交接级别**：实测可用于短时数据采集；尚未长时间无人值守验收。

## 一、范围与版本基线

该模块源自 `test/record80_20261024` 的**最后一版经过板端实际录像验证的源文件**，不是原先另一台Windows电脑下的 `gc4653_36mhz_80fps_20261019/board_record80`。原实验不做移动/删除。

原实测二进制SHA-256：

```text
3d751f2b2c16b0b0815453593689d5b96bd1d4375c667f37836846edf3600cba
```

复用已验证的 `test/clock36_live_20261023` SG2002/GC4653摄像头链路：CAM1 ÷33（父时钟1187999988Hz，计算MCLK约36MHz）、VI 1280×720 约80FPS、`PT_JPEG` 的VENC Q85编码、HTTP MJPEG预览。**不得以保留80FPS为理由将相机重置为旧37.125MHz全速方案**，旧方案曾出现顶部彩条。

模块化只重定位源文件、构建脚本、部署脚本和监督脚本；**不修改**摄像头SDK底层初始化、MIPI、ISP VENC逻辑与原工程历史归档。

## 二、目录、依赖和部署

### 本地工程

```text
D:\study\LicheeRV
├─ modules\record80                    <-- 正式可复用录像模块
│  ├─ README.md                         <-- 功能、最短使用入口
│  ├─ src
│  │  ├─ camera_36record.cpp            <-- Camera VI/VENC + HTTP
│  │  └─ record80.h                     <-- AVI writer / recording queue
│  ├─ scripts
│  │  ├─ build.sh                       <-- 交叉编译
│  │  ├─ deploy.ps1                     <-- 上传 + hash校验
│  │  ├─ run_board.sh                   <-- 板端监督
│  │  ├─ sync_recordings.ps1            <-- 视频下载回项目
│  │  └─ extract_frames.ps1             <-- 训练图片抽帧
│  ├─ docs
│  │  ├─ USER_GUIDE.md
│  │  ├─ HANDOFF.md
│  │  └─ TEST_REPORT.md
│  ├─ bin\camera_36record               <-- RISC-V ELF构建产物
│  ├─ build\                            <-- 构建临时.o，未加入版本控制
│  ├─ captures\                         <-- 下载的AVI/JSON，首次同步时创建
│  └─ dataset_frames\                   <-- 抽帧图片，首次抽帧时创建
├─ test\record80_20261024              <-- 验证过程证据，不作为日常入口
└─ test\clock36_live_20261023          <-- 之前的80FPS稳态方案，只读保留
```

依赖于仓库内本地存在的 `speed-fry/workspace/LicheeRV-Nano-Build`、`speed-fry/workspace/camera`，包括匹配SG2002 SDK的 `sample_common_*.c`、GC4653 Sensor源码、RISC-V GCC10.2工具链、MMF/ISP/VENC用户态动态链接板库。外部SDK不能从公开Git仓库自动获得。

- 构建：`bash /mnt/d/study/LicheeRV/modules/record80/scripts/build.sh`（WSL）。
- Windows部署：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\study\LicheeRV\modules\record80\scripts\deploy.ps1"`。
- 新的板端**持久部署路径**：`/code/camera/modules/record80/`，与原先仅在 `/tmp/clock36_record_20261024/` 存放的验证版不同。
- 录像文件：`/code/camera/recordings/`，移动/下载到本地使用 `scripts/sync_recordings.ps1`，不将视频混在源码目录。
- 日志目录：`/code/camera/modules/record80/record_report/session_<boardtime>_<shellpid>/`。
- 板端 `/code/camera/bin/camera_http80` 和旧 `/tmp/clock36_live_20261023` 均未被替换。

## 三、录像数据流与线程

```text
GC4653 ──CSI/MIPI──> SG2002 VI (1280×720, ~80fps)
                          |
                    latest VI frames
                          |
                    Hardware VENC JPEG Q85
                          |
            ┌─────────────┴──────────────┐
            |                            |
     JPEG latest-frame buffer        every second JPEG
            |                            |
   HTTP MJPEG :8081               bounded queue(32)
            |                            |
    browser preview                AVI writer thread
                                         |
                                 RIFF AVI/MJPG + idx1
                                         |
                             .avi.part → .avi + .avi.json
```

参考实现：
- `src/camera_36record.cpp`：`encoder_worker()`接VI帧并驱动单路硬件VENC，`record_control_server()`提供状态、开始和停止，`http_server()`提供浏览器实时画面；VENC失败5次终止。采集线程与写盘线程不共享可变视频缓冲。
- `src/record80.h`：`MJPEGRecorder`的 `push()` 只复制入队，最多32帧，队列满则增加 `dropped`；写线程进行 AVI 标头、每帧chunk写入、`idx1`索引、头字段回填和最终 `rename`。录像文件单段最长60秒或350MiB。
- `scripts/run_board.sh`：在CAM1原分频值 `0x00200001`、温度<70°C、无冲突进程/锁的条件下启动；基线RAW抓取后改为 `0x00210001`；每3秒温度/MIPI监控。退出时将时钟恢复为原值、释放锁，另有超时保护。
- 录制时会出现 `{"requested":true,"recording":false}` 的短暂过渡状态，不等于录像已经开始。

### HTTP接口

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `http://10.133.124.1:8081/` | 网页预览、按钮UI（只能一名MJPEG长连接观众） |
| GET | `/live.mjpg` | 1280×720 JPEG MJPEG流 |
| GET | `/snapshot.jpg` | 单帧JPEG |
| GET | `http://10.133.124.1:8082/status` | 录像状态JSON |
| POST | `http://10.133.124.1:8082/start` | 请求开始录像 |
| POST | `http://10.133.124.1:8082/stop` | 请求停止并封段 |

8081和8082都绑定板端USB网口 `10.133.124.1`（不是所有网络接口）。**无HTTP鉴权、无TLS，不能直接开放到公网/不可信LAN**。

状态字段：
`requested`、`recording`、`file`、`last`、`written`、`dropped`、`bytes`、`segments`、`write_errors`、`elapsed`、`error`。

录像成功在同目录生成 AVI 与JSON，JSON含 `codec`、`width`、`height`、`nominal_fps`、`capture_target_fps`、`frames`、`elapsed_sec`、`fps_by_elapsed`、`jpeg_bytes`、`queue_drops`、`write_errors`。

## 四、已证实的能力与明确限制

1. **已实测80FPS采集**：这说的是VI/PTS取流；并非录像帧率。
2. **录像按目标40FPS**：在原设备短测中951帧 / 24.682s =38.53fps；队列无丢帧，计数不包含在取样前被JPEG线程替换的VI帧。
3. **数据吞吐上限**：板端磁盘64MiB顺序写入用时7.60s，约8.4MiB/s；对1280×720 JPEG Q85高运动内容，80FPS需要约11MiB/s以上，不应承诺全80FPS无丢帧写入。
4. **AVI是恒定40FPS时间轴**：真实录制38.5FPS会导致回放时长略短；做静态图片YOLO训练可直接抽帧，但若用于时间敏感动作识别，要把单帧monotonic/PTS写入索引或旁路元数据。
5. **AVI不是RAW无损**：JPEG Q85为有损，无法保留传感器原始Bayer RAW12像素。
6. **板端RTC显示1970**：文件名时间戳不可信；需以后独立修复NTP/RTC，不影响单调时间FPS统计。
7. **短时试验到~24秒已验证**：60秒分段与最大5分钟录像长测、磁盘空间不足测试、断电恢复测试均未完成，不要标为生产可用。
8. **相机约36MHz未物理示波器实测**：寄存器÷33基于1187999988Hz父时钟推算；正式产品应实现匹配内核时钟驱动，避免MMIO临时改动。
9. **温度/网络**：实测温度峰值72.8°C附近；大负载/密封外壳需要散热与退避。HTTP浏览器长连接可能导致页面误以为“卡”，录制API独立。

## 五、验证、版本管理和回退

变更后最少完成以下检查，不可只看编译通过就告诉用户已经上板：

```bash
# WSL：检查两份shell脚本语法、完整交叉编译
bash -n /mnt/d/study/LicheeRV/modules/record80/scripts/build.sh
sh -n /mnt/d/study/LicheeRV/modules/record80/scripts/run_board.sh
bash /mnt/d/study/LicheeRV/modules/record80/scripts/build.sh
```

部署后读取板端SHA；检查没有其他Camera进程；板端温度 <70°C 才进入监督脚本；验证网页200、`/status`状态、POST start/stop、录制成品AVI+JSON、`ffprobe`帧数与JSON匹配、解码出图、`dropped=0`且 `write_errors=0`；最后检查分频寄存器回 `0x00200001`、锁清理以及MIPI无新增错误。

**原始验证证据**：`test/record80_20261024/README.md`、`test/record80_20261024/web_control_test.log`、`test/record80_20261024/captures/`，详情见 `docs/TEST_REPORT.md`。不要删除这批实验文件。

**整理后的模块已独立上板验证**：2026-10-24 使用模块脚本完整重新编译，RISC-V程序SHA-256与原实测版完全一致，`deploy.ps1`部署到 `/code/camera/modules/record80` 并核对哈希；通过新路径 `run_board.sh` 自动录制 **961帧、24.767秒、平均38.802FPS、队列0丢帧、写入0错误**，FFprobe识别961帧。监督运行最后分频恢复 `0x00200001`，MIPI无新增错误。此实测记录已补充到 `docs/TEST_REPORT.md`。

若新模块出现问题：
1. 在板端终端使用 `Ctrl+C` 或让监督脚本计时到点正常退出；确认 `devmem 0x030028c4 32` 为 `0x00200001`、锁不存在；
2. 保留当次 `record_report/session_*/capture.log` 和录像元数据，不要盲删；
3. 当前模块停止后再切回 `test/clock36_live_20261023` 原版运行入口，**同一时间只能有一条取流链路**；
4. 若需回退到最后一次录像实验版，可在板端使用 `/tmp/clock36_record_20261024`，但 `/tmp` 文件在重启后可能消失；原版研究程序不依赖本模块。

## 六、后续开发优先级

- 验证60秒AVI自动分段及多段连续性；强制手动停止与断电/异常恢复；修复板端时间。
- 如果目标必须 **80FPS完整录像**，应**单独实验**SG2002 H.264/H.265硬件编码/硬件VI-VENC绑定或更快外部存储，不能直接更改目前已验证的Q85视频源。测试VENC并发和内存使用，保留失败自动回退。
- 按真实镜头采集不同光照、遮挡、尺寸的训练视频；在PC GPU训练YOLO，导出ONNX，使用匹配SG2002 NPU SDK编译 CVIMODEL 后测试。这一阶段尚未完成，推理FPS不能套用相机采集FPS。
- 做稳定运维前需鉴权、日志大小管理、SD剩余空间告警与录像目录清理策略，但**未经用户同意不自动删除历史视频**。
