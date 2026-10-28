# 录像模块使用手册

## 网页断线与 SSH 转发提示

摄像头退出后，SSH 连接与本地端口转发可以仍然存在。如果浏览器继续请求已经停止的 8081/8082 服务，SSH 会输出 `channel ... open failed: connect failed: Connection refused`；这不表示摄像头仍在运行。在板端 shell 提示符下按 Ctrl+C 不会关闭笔记本上的 SSH 转发。

新版网页在状态请求失败、3 秒超时或预览图片报错后停止自动轮询、移除预览并禁用录像按钮，显示“重新连接”。确认摄像头重新启动后再点击该按钮。断线瞬间已经发出的请求仍可能产生少量 SSH 提示，但不应每秒无限重试。浏览器的 MJPEG 断流事件存在差异，状态轮询也用于检测服务停止。

这里只停止网页请求，不会擅自停止板端录像或摄像头；网络故障时不能把网页“断开”提示当作板端录像已经结束，仍应通过 SSH 和板端日志确认。

升级前已经打开的旧网页仍执行旧脚本，必须关闭旧标签页，启动新版程序后重新打开。结束观看时关闭预览标签页；如不再需要 SSH，在板端 shell 执行 `exit` 退出对应连接。不要通过修改 sshd 或屏蔽日志来掩盖连接失败。

适用：LicheeRV Nano SG2002 + GC4653；当前已验证的笔记本项目为 `D:\study\LicheeRV`。

## 1. 录像到底是什么规格？

| 项目 | 实际含义 |
|---|---|
| 摄像头采集 | VI/PTS **约80FPS**，1280×720 |
| 录像取样 | 每两张硬件JPEG取一张，目标**40FPS** |
| 实测短测录像 | 平均**38.53FPS**（24.682s录下951帧） |
| 单帧画质 | 已有JPEG VENC Q85，1280×720，**不是无损RAW** |
| 视频格式 | MJPEG AVI，可使用FFmpeg、OpenCV读取 |
| 输出位置 | **板端** `/code/camera/recordings/` |
| 自动分段 | 满60秒或约350MiB时封一段 |
| 保护措施 | 空间低于150MiB拒绝新录制；摄像头独占、温度、MIPI监控、临时时钟恢复 |
| 运行时长 | 由 `config/record80.yaml` 中 `max_run_sec` 控制，允许20~300秒；超过自动关停（5分钟连续录像尚未验收） |

AVI视频头按固定40FPS声明；如数据采集实际未达到40FPS，播放时间可能短于真实拍摄时间。用于YOLO抽帧/目标框标注通常没问题，**需要动作精确时序的训练须另做时间戳版本**。

## 2. 部署（只需部署一次；重装系统后需要重新部署）

以下步骤在笔记本执行，看到提示符如 `PS C:\Users\kalapaopao>`；**不是**荔枝派 `#` 提示符。

先检查是否能免密连接板端（两条USB网络地址可能随连接方式不同）：

```powershell
ssh root@10.133.125.1 "uname -m"
```

预期返回 `riscv64`。第一次部署/重新部署：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\study\LicheeRV\modules\record80\scripts\deploy.ps1"
```

该脚本：从 `modules\record80\bin\camera_36record` 上传到板端持久目录
`/code/camera/modules/record80`，同时上传监督脚本和 YAML，核对二进制 SHA-256、检查脚本语法与配置；旧版文件保留在板端 `backup_...` 目录。
它**不会自动占用摄像头或开启录像**，不覆盖原来的 `camera_http80`。

若需要在本笔记本重新编译（编译后需重新部署），在 Windows 命令行中：

```powershell
wsl.exe -- bash -lc "bash /mnt/d/study/LicheeRV/modules/record80/scripts/build.sh"
```

需要 `speed-fry/workspace` 配套Sipeed SDK、板库、RISC-V musl交叉编译器，缺少这些环境不可仅用本文件夹构建。

## 3. 运行并录像（荔枝派端）

以下命令在 `ssh root@10.133.125.1` 登录后的板端 `#` 终端中执行：

启动前先编辑板端 `/code/camera/modules/record80/config/record80.yaml`（或修改本机同名文件后重新部署）。配置项和范围见[调参说明](CONFIG.md)。**修改只在下次启动生效，不支持运行中热更新。**

先校验，不占用摄像头：

```sh
sh /code/camera/modules/record80/run_board.sh --check-config
```

推荐的唯一启动命令：

```sh
sh /code/camera/modules/record80/run_board.sh
```

正式入口现在直接读取YAML中的`black_level_mode`及四通道值。使用`manual`和四个256时，启动输出应包含`black_level_mode=manual blc=256,256,256,256`，运行日志应有`RECORD80_BLC_SET ... readback_match=1`及`RECORD80_BLC_VERIFY ... match=1`。之前独立诊断照片的BLC设置已接入此入口，不要再把未修正的旧二进制与诊断程序混用。详见[黑电平配置及回退](CONFIG.md)。

如需临时复现旧的24秒自动录像测试，可使用兼容环境变量（不改 YAML）：

```sh
MAX_RUN_SEC=24 RECORD_TEST_AUTOSTART=1 sh /code/camera/modules/record80/run_board.sh
```

脚本会先检查温度、寄存器值和其他进程是否占用，再初始化摄像头，7秒后验证首帧；切换CAM1到÷33，约36MHz；启动录像。达到指定时长后自动停止录像、封装AVI、恢复摄像头时钟并释放共享锁。

**手动开始/停止录像：** `auto_record: false` 时，在最长 `max_run_sec` 运行窗口内使用网页按钮。旧环境变量启动方式仍兼容：

```sh
MAX_RUN_SEC=300 sh /code/camera/modules/record80/run_board.sh
```

保持这个终端打开，在本笔记本 Edge 访问：

- 网页预览和按钮：<http://10.133.124.1:8081/>
- 录像状态接口：<http://10.133.124.1:8082/status>

在页面点击「开始录像」，确认有计数，再点击「停止录像」。网页持续推送MJPEG可能占网络，录制帧和页面渲染帧率不是一个指标。

不用浏览器也可在**笔记本 PowerShell**操作：

```powershell
curl.exe -X POST http://10.133.124.1:8082/start
curl.exe http://10.133.124.1:8082/status
curl.exe -X POST http://10.133.124.1:8082/stop
```

如果已经SSH进入板端（提示符 `#`），使用**Linux**命令，不存在 `curl.exe`：

```sh
curl -X POST http://10.133.124.1:8082/start
curl http://10.133.124.1:8082/status
curl -X POST http://10.133.124.1:8082/stop
```

注意 `{"accepted":true}` 只意味着请求被接受；进一步查状态字段 `recording`、`written`、`dropped`、`write_errors` 以确认真的录下视频。

**停止整个摄像头程序：** 在启动监督脚本的终端按 `Ctrl+C`，让脚本自行退出；**不要 `kill -9`、不要手动删除锁或强制改时钟寄存器**。

## 4. 查找、下载与抽帧

在板端：

```sh
ls -lh /code/camera/recordings/*.avi
ls -lh /code/camera/recordings/*.avi.json
df -h /code/camera/recordings
```

录像文件如 `gc4653_19700101_005208_1290_0001_720p40.avi`。
⚠️ 板端RTC目前显示1970年，所以文件名日期不是本次实际日期；单调时钟的FPS测量不受影响。

在笔记本 PowerShell 运行同步工具（已下载文件不重复下载），一律保存到本项目：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\study\LicheeRV\modules\record80\scripts\sync_recordings.ps1"
```

结果在 `D:\study\LicheeRV\modules\record80\captures`。默认下载全部尚未下载的已完成录像；若只需要指定文件，可加 `-NamePattern 'gc4653_19700101_010011_*'`。传输前请检查板端剩余空间，录像很占容量。

已经安装 Windows FFmpeg 后，使用模块自带抽帧工具，每秒抽 5 张用于 X-AnyLabeling/YOLO：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\study\LicheeRV\modules\record80\scripts\extract_frames.ps1" -Video "D:\study\LicheeRV\modules\record80\captures\你的录像.avi" -ExtractFps 5
```

图像输出 `modules\record80\dataset_frames\录像名\frame_000001.jpg`。如本机没有FFmpeg请先准备可用的FFmpeg可执行文件；**抽帧脚本属于辅助功能，未计入板端实测通过项。**

可用板端FFprobe核对 AVI头中帧数：

```sh
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,nb_frames,r_frame_rate -of default=noprint_wrappers=1 /code/camera/recordings/你的录像.avi
```

## 5. 常见故障与处理

| 情况 | 解释 / 处理 |
|---|---|
| `camera_36record: not found` | 尚未运行 `deploy.ps1` 或板端程序丢失；先核查 `/code/camera/modules/record80/camera_36record` |
| `BAD_RECORD80_CONFIG` | YAML 不符合本项目支持的简单 `key: value` 格式或数值越界；先运行 `--check-config`，不得绕过校验 |
| `CAMERA_PROCESS_BUSY` / `CAMERA_LOCK_BUSY` | 其他摄像头进程占用VI；正常停止旧进程，不能直接强删锁 |
| 启动马上退出、显示温度 | 监督脚本要求**启动前 <70°C**；让设备冷却，不能绕过温控 |
| `FATAL_TEMP_LIMIT` | 超过74.5°C，监督脚本中止并执行时钟恢复 |
| `FATAL_NEW_MIPI_ERROR` | MIPI错误计数出现新增，故保护性退出；须排查硬件、时钟、信号 |
| 网址打不开 | 程序必须仍运行；确认USB网段与 `10.133.124.1` 网卡状态、8081/8082端口 |
| 页面在动、没有录像 | 检查 `/status` 的 `recording` 与 `written`，两套是独立流程 |
| `*.avi.part` | 还没正常封装，或发生异常退出；不要把 `.part` 当已完成AVI |
| 录像写入变慢 | 检查 `dropped`、`write_errors`、`df -h`；慢存储不能强求80FPS原质量录像 |
| 录像播起来稍快 | AVI标记40FPS，而真实取帧可能约38.5FPS；以后若做严格时序需另加时间戳 |
| 录像文件日期1970 | 板端RTC/NTP问题，不代表录制发生在1970年 |

## 6. 数据采集建议

- 每段拍摄同一场景的不同距离、角度、亮度、遮挡与运动轨迹；录像后先抽帧看画质再标注。
- 采集40FPS就足以为静态物体识别大量抽帧，标注时无需逐帧标注全部重复画面。
- 录像与推理是独立目标，**当前没有完成 YOLO 在板端同步运行的性能测试**；不要混淆取流80、录制约38.5、推理未知。
- 本服务未做鉴权，仅允许在可信USB网络测试，不建议向公网开放8081/8082。
