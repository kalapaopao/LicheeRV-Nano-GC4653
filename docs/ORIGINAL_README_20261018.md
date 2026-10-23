# 荔枝派摄像头：启动、实时查看、停止

> **条纹排查更新（2026-10-18）**：80 档顶部彩条已在 ISP 之前的 Bayer RAW 中复现；60 档对照未见，切回 80 档再次出现。关闭 VI 压缩、TNR 和 DPC 均不能消除，排除了网页/USB/JPEG 编码为其生成源。当前定位为这套模组、驱动与高速时钟档的采集兼容问题；尚不能区分传感器内部时序与 MIPI 接收的具体电气原因。详细样本、失败记录和回退见 [条纹排查报告](../speed-fry/stripe-diagnostic/REPORT.md)。**仍保留原 80 档运行，条纹未修复，不等于画质验收通过。** 若优先要求无此彩条，可按下文原有命令显式切换 60 档；没有裁剪或模糊隐藏问题。

## 先分清三个帧率

- **采集帧率**：板端从 GC4653/VI 实际取到多少帧，日志字段 `host_fps` / `pts_fps`。
- **编码帧率**：硬件编码器实际产出多少张完整 JPEG，日志字段 `encode_fps`。
- **网络接收/显示帧率**：笔记本实际收到多少帧，和浏览器/屏幕真正显示多少帧是两件事。接收测试见 `speed-fry/preview-hd-receive.json`；没有测量浏览器绘制帧率，不能把网络接收数当成显示数。

**现在的目标是 80 档采集＋不限 30 FPS 的完整 720P 预览。** 前一版 60 档接收约 24.7 FPS、80 档接收约 27.5 FPS，那是旧版的实测值，不是网页的帧率上限。当前新增版本已经移除预览程序中约 30 FPS 的抽帧限制，使用硬件逐帧 JPEG 接口，不设置 MJPEG 目标帧率；实际性能仍以测试与日志为准。

80 档原始图中曾发现顶部彩色条纹；上一轮 60 档样本未见此条纹。80 档性能测试成功不代表画质验收通过。程序不会通过裁掉条纹或缩成低分辨率来掩盖问题。

## 本次新版实测

保持完整 1280×720、Q85，没有降低清晰度：

| 版本 / USB 通道 | VI 取帧 | JPEG 编码 | 笔记本接收 |
|---|---:|---:|---:|
| 旧版 60 档、30 FPS 抽帧目标 | 60 FPS | 约 25 FPS | 约 24.7 FPS |
| 旧版 80 档、30 FPS 抽帧目标 | 82.5 FPS | 约 27.5 FPS | 约 27.5 FPS |
| 新版 80 档、RNDIS | 82.5 FPS | 约 81 FPS | 58.85 FPS（20 秒） |
| 新版 80 档、NCM | 82.5 FPS | 约 82.5 FPS | 82.50 FPS（20 秒）；82.43 FPS（60 秒） |

**最后保留运行的是 80 档 + NCM，不是 60 档。** 60 秒测试收到 4947 帧、4947 个不同 JPEG 哈希。当前板卡/镜像/连接实测通过，不代表数小时长稳或所有场景的性能上限。浏览器真正绘制 FPS 未测，显示还受解码和屏幕刷新率限制。80 档顶部条纹仍存在，图像质量未完全验收。

## 1. 连接并登录（笔记本 PowerShell）

使用可传数据的 USB 线连接荔枝派，等待系统启动和 USB 网卡出现。本次设备地址：

```powershell
ssh root@10.133.125.1
```

按板端提示输入密码，输入时不会显示字符。这个命令是在 **Windows PowerShell** 执行的。

板端 `/code/camera` 与 Windows 的 `D:\study\LicheeRV` 不是同一个目录。下面以 `/code/` 开头的命令都在 **SSH 登录后的荔枝派终端** 执行，不能在 Windows 的 `D:\` 下直接运行。

如果无法连接，先在 PowerShell 查看：

```powershell
Get-NetIPAddress -AddressFamily IPv4
```

本次 RNDIS 主机地址是 `10.133.125.100`，板端是 `10.133.125.1`，可继续用于 SSH；NCM 主机地址是 `10.133.124.100`，板端是 `10.133.124.1`，当前预览使用 NCM。USB 网卡地址不是 WLAN/VPN 地址。若镜像或 USB 地址改变，需要同步调整高清脚本中的绑定 IP 和查看地址，不能盲扫其他网络。

## 2. 启动 80 档实时画面（荔枝派终端）

```sh
sh /code/camera/scripts/start-preview-hd.sh 80 10.133.124.1
```

- 使用原有 GC4653 80 档，完整 1280×720，硬件逐帧 JPEG 编码组成 MJPEG 视频流，JPEG quality=85。
- 新版不再主动按 30 FPS 抽帧；编码/网络慢时只保留最新待处理画面，不无限排队累积延迟。
- 命令启动后台任务后返回终端，**返回不代表初始化已成功**。等待约 5–10 秒并检查第 5 节日志。
- 第一个参数 `80` 是采集档位，第二个参数 `10.133.124.1` 选择 USB NCM 高速通道。为兼容旧调用，省略第二个参数仍绑定 RNDIS 的 `10.133.125.1`；请照抄本文完整命令，不要省略 IP。
- 这是基于官方 MMF/VENC 接口适配的项目程序，不是原封不动的官方网页 Demo。

## 3. 在笔记本上查看（浏览器）

直接打开：

**http://10.133.124.1:8081/**

其他入口：

- 直接视频流：http://10.133.124.1:8081/live.mjpg
- 单张原尺寸图片：http://10.133.124.1:8081/snapshot.jpg
- 本地快捷页面：双击 `speed-fry/view-preview-hd.html`。

**不要再打开旧 `8080` 页面**，那是之前的缩略预览，不是当前高清入口。

当前只支持一个持续预览客户端。只保留一个视频标签页；不要同时用浏览器、播放器和接收测试脚本连接。`snapshot.jpg` 不会实时刷新；看实时画面应打开首页或 `live.mjpg`。浏览器页面本身不会切换 60/80 档，档位由板端启动命令决定。

## 4. 关闭画面、停止程序、切换档位

### 只关闭浏览器标签页

这只断开查看，**板端仍继续采集、编码**。重开上述地址即可再查看。

### 真正停止采集和推流（荔枝派终端）

```sh
sh /code/camera/scripts/stop-preview-hd.sh
```

看到 `Normal shutdown requested` 表示已请求正常停止，等待约 3 秒再检查：

```sh
ps | grep '[c]amera_preview_hd'
test ! -d /code/camera/run/lock && echo 'Camera lock released'
```

没有预览进程，且输出 `Camera lock released`，表示可以重新启动。如果仍有进程/锁，先看日志等待正常退出；**不要直接删锁、重复启动或 kill -9**。

### 切换为 60 档（画质对照，不是默认性能方案）

```sh
sh /code/camera/scripts/stop-preview-hd.sh
sleep 3
sh /code/camera/scripts/start-preview-hd.sh 60 10.133.124.1
```

切回 80 档：

```sh
sh /code/camera/scripts/stop-preview-hd.sh
sleep 3
sh /code/camera/scripts/start-preview-hd.sh 80 10.133.124.1
```

若启动提示 `Camera is busy`，说明摄像头尚未释放或有其他采集任务。先确认状态，不要越过互斥锁。切换后刷新网页，地址仍为 `8081`。

### 退出 SSH、板子重启/断电

- 关闭 SSH 窗口或输入 `exit` **不会停止后台预览**。
- 此预览**没有设置开机自启**。板子正常关机或断电后程序就结束；重新上电后需再次 SSH 登录并执行启动命令。
- 建议先正常停止预览，再按板子现有方式正常关机；不要在写日志/抓图时直接拔电。本文不执行关机、重启或更改自启配置。

## 5. 确认当前是 60 还是 80，以及实际速度

在荔枝派终端执行：

```sh
ps | grep '[c]amera_preview_hd'
head -3 "$(cat /code/camera/run/preview-hd.report)/run.log"
tail -10 "$(cat /code/camera/run/preview-hd.report)/run.log"
```

- 进程参数末尾 `80` / `60` 就是所选档位。
- 日志开头 `sensor_mode=80` 表示 80 档，`preview_limiter=none` 表示新版本没有旧的 30 FPS 抽帧限制。
- `host_fps` / `pts_fps`：实际取帧率，不是命令中的请求值。
- `encode_fps`：最近统计周期内实际编码速度。
- `sent_fps`：最近周期内向客户端发出的速度；没有客户端时为 0。它不代表浏览器绘制 FPS。
- `jpeg_mbit_s`：JPEG 负载传输速率，不含网络协议开销。
- `preview_replaced`：来不及编码而被更新帧替换的数量，非 0 说明编码/调度未跟上全部取帧。
- `duplicate_pts`、`timeouts`、`encode_errors`：分别是重复/倒退 PTS、取帧超时、编码错误，应关注它们是否持续增长。
- 启动后的第一个周期含热身影响；不要用第一个速率判断稳定性能。

持续查看（`Ctrl+C` 仅退出日志查看，不停止后台预览）：

```sh
tail -f "$(cat /code/camera/run/preview-hd.report)/run.log"
```

## 6. 黑屏、旧画面或打不开怎么办

1. 确认 USB 数据线及板端 IP，先确保能 SSH 登录。
2. 确认打开的是 `8081`，不是旧 `8080` 或单张图片 `snapshot.jpg`。
3. 按第 5 节确认进程和日志。若初始化失败，再看启动器日志：

   ```sh
   cat /code/camera/run/preview-hd-launch.log
   ```

4. 关闭其他预览标签页、播放器和接收测试脚本，几秒后重新打开首页。持续视频客户端会独占当前 HTTP 服务。
5. 切档或停止后浏览器可能停在最后一帧，这是断开的旧画面，不是程序仍运行；刷新并检查板端状态。
6. 80 档若有顶部条纹，可正常停止后切 60 档作对照。不要把它当成通过改网页放大比例就能修复的问题。

## 7. 文件在哪里、如何回退

Windows 保存目录：`D:\study\LicheeRV\speed-fry`。WSL 对应 `/mnt/d/study/LicheeRV/speed-fry`。

- `camera_preview_hd.cpp` / `camera_preview_hd`：当前完整 720P 硬件预览源码/板端程序。
- `start-preview-hd.sh`、`stop-preview-hd.sh`：启停脚本本地副本。
- `build-preview-hd.sh`：使用包内 SDK/工具链在 WSL 构建，不是在 Windows 直接运行的脚本。
- `saved-80/`：已验证原 80 档采集程序、源码、脚本和校验值。
- `report-80/`：原 60 秒约 82.37 FPS 的纯采集报告；**不是实时预览的性能报告**。
- `preview-hd-receive.json` / `preview-hd-run.log`：最近一次高清接收测试和板端日志副本。旧报告不自动刷新，实时状态以板端日志为准。
- `PREVIEW-HD.md`：官方/社区参考、方案、早期测试和失败记录。
- `hd-before-unlimited/`：移除 30 FPS 限制前的高清程序/源码备份，用于对照，不要与新入口同时运行。

板端程序：`/code/camera/bin/camera_preview_hd`；启停脚本：`/code/camera/scripts/`；每次运行单独生成 `/code/camera/reports/preview-hd-*`。

停止高清预览即回到原功能，无需恢复系统库/配置。停止后要复测原程序：

```sh
cd /code/camera
sh scripts/benchmark.sh 80 60
```

这条命令是 **80 档、测试 60 秒的纯采集**，不是 60 FPS，也不会开启网页。与网页预览互斥，不要同时运行。

本操作不刷机、不替换系统库、不修改传感器原驱动、不安装依赖、不设置自启。当前目录不是 Git 仓库；不要用 Git 重置或清理来恢复本任务。保留程序/源码备份即可单独回退新增预览，不影响原采集入口。
