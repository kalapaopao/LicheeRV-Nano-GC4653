# 原尺寸硬件编码预览

> 2026-10-18 条纹专项：已抓取未压缩 Bayer RAW，80 档顶部异常在 ISP 之前即存在，60→80 反向对照再次复现。关闭 VI 压缩、TNR、DPC 均无效。详见 [完整排查报告](stripe-diagnostic/REPORT.md)。正式程序、驱动与默认 80 档已恢复；没有把诊断开关带入正式程序，没有宣称画质修复。

> 最新操作入口统一见根目录 `D:\study\LicheeRV\README.md`。当前运行 **80 档 + USB NCM，http://10.133.124.1:8081/**，60 秒接收实测 **82.43 FPS**。下文约 25/27 FPS 是旧版抽帧预览的历史对照，不是网页极限。当前已使用 `PT_JPEG` 逐帧编码并取消抽帧限制。

## 不限抽帧版本的失败与调整

已去掉应用层 `next=t+1/30` 抽帧，并增加实际 `encode_fps`、`sent_fps`、`jpeg_mbit_s`、待编码帧被替换计数。原传感器寄存器和程序仍不改变，输出保持完整 1280×720、Q85。

直接请求 MJPEG 80 目标帧率时创建通道失败，`CVI_ERR_VENC_NOT_SUPPORT (0xc0078008)`，第一次接收测试因此连接被拒绝。内核日志明确为 `_cviCheckFrameRate ... fr32DstFrameRate=0x50, not support`。该结果仅证明当前驱动拒绝这个参数，不能直接断言 JPEG 硬件或浏览器最多只能 30 FPS。

随后改用官方 SDK 支持的 `PT_JPEG` / `VENC_PIC_RECEIVE_SINGLE`，每张帧 `StartRecvFrame(1)` → `SendFrame` → `GetStream` → `ReleaseStream` → `StopRecvFrame`，用 `GetJpegParam/SetJpegParam` 配置 Q85，不通过写假的帧率参数绕过检查。原拒绝日志保存为 `preview-hd-unlimited-80-rejected.log`。主线程持续取帧，单槽待编码队列保证慢端不累积无限延迟。

此版本替换了本任务新增的高清预览入口；修改前源码/二进制保存在 `hd-before-unlimited/`。原 80 档纯采集程序 `saved-80/` 和板端原 `camera_bench` 均保留。停止预览可回到原纯采集功能。

### 不限抽帧版的最终实测

- 80 档 + RNDIS（10.133.125.1）：VI 约 82.5 FPS，编码约 81 FPS，20 秒收到 1178 帧、58.85 FPS。
- 同一程序、1280×720/Q85，改用已启用的 NCM（10.133.124.1）：20 秒收到 1651 帧、82.50 FPS；60 秒收到 4947 帧、82.433 FPS、4947 个不同 JPEG 哈希。VI/PTS 约 82.5 FPS、编码约 82.5 FPS，重复 PTS、取帧超时、编码错误均为 0。
- `preview_replaced` 非零（含首帧保存及初始阶段），不宣称所有取帧均无遗漏传到电脑。浏览器绘制 FPS、逐帧光学唯一性、数小时长稳未验证。80 档条纹保留。
- 以上是通道对照实测，尚未逐项测量 RNDIS 内核/协议/CPU 开销，不能据此断言所有 RNDIS 设备都最多 59 FPS。
- 证据：`preview-max80-rndis-receive.json`、`preview-max80-rndis-run.log`、`preview-max80-ncm-20s-receive.json`、`preview-max80-ncm-60s-receive.json`、最新 `preview-hd-run.log`。最后保留 NCM 监听，没有安装或修改 USB 驱动。
- 执行：WSL 构建、HD 停止/部署/状态查询、内核日志尾部排查、RNDIS/NCM 20 秒与 NCM 60 秒有界接收、语法检查。初次 MJPEG 80 配置失败和连接拒绝已记录；WSL 仍有已有配置/PATH 警告，根目录非 Git 仓库，`git status` 失败。未读取 Git 历史。
- 新增根目录 `README.md`、`hd-before-unlimited/` 备份和对照结果；修改新增预览源码/二进制、辅助脚本、快捷页、说明，更新编译对象。无删除/移动文件、无原驱动/系统库/配置修改。原方案增加了 JPEG API 和 NCM 对照，仍在当前实时预览链路内，可通过正常停止回退到原采集功能。

## 依据与方案

已查阅：
- 官方 MMF 开发指南：https://wiki.sipeed.com/hardware/zh/lichee/RV_Nano/8_mmf_development_guide.html
- 官方编码样例：https://github.com/sipeed/LicheeRV-Nano-Build/blob/main/middleware/v2/sample/common/sample_common_venc.c
- 社区同板 CSI/MJPEG 示例：https://github.com/ret7020/LicheeRVNano/tree/master/Projects/MJPEGStream
- 官方仓库 sample_venc 使用反馈：https://github.com/sipeed/LicheeRV-Nano-Build/issues/97
- 用户提供本地 `D:\study\LicheeRV\stereo_capture.cpp`。
- 官方相机说明：https://github.com/sipeed/MaixPy/blob/main/docs/doc/en/vision/camera.md ，其中明确提示部分组合 80 FPS 可能有图像异常，可尝试退回 60 FPS。

官方示例使用 VENC 的 `CreateChn`、MJPEG FIXQP、`StartRecvFrame`、`SendFrame`、`GetStream`、`ReleaseStream` 等接口，并按每包 `u32Offset/u32Len` 读取码流。本实现按相同接口和字段约定适配当前原工程，不是直接运行未经审核的第三方二进制。

社区例子依赖 OpenCV-mobile，`MJPEGWriter.cpp` 使用 `imencode`，主程序还会转成灰度；没有为了套用例子安装或替换 OpenCV。仅参考其 HTTP multipart 传输思路，本次采用当前 SDK 的硬件编码接口以避免软件编码和像素缩略的性能/画质折中。

`stereo_capture.cpp` 面向 V4L2 的 `/dev/video33`，输入 MJPEG/YUYV，按左右/上下拆双目图片，没有窗口或网络推流；不能替代当前单目 GC4653 的 CVI VI/ISP 初始化。其实际尺寸检查、序号统计思路可参考。未修改该文件。它未检查设置 FPS 的返回值，打印的 fps 只是请求值；时间戳是否单调时钟也需检查后才能算延迟。

## 当前入口

板端：

```sh
sh /code/camera/scripts/start-preview-hd.sh 80 10.133.124.1
```

默认保留 80 档，可显式使用 `start-preview-hd.sh 60` 或 `start-preview-hd.sh 80` 切换；先正常停止当前入口，再切换。该选项只使用驱动已有 27 MHz/37.125 MHz 配置，不超频或改系统配置。

历史画质对照曾保留 60 档，现已按用户要求切回 **80 档 + NCM**。省略第二个 IP 参数仍兼容旧 RNDIS 绑定；要使用本次最快通道，请完整填写上面的命令。

笔记本：

```text
http://10.133.124.1:8081/
http://10.133.124.1:8081/live.mjpg
http://10.133.124.1:8081/snapshot.jpg
```

停止：

```sh
sh /code/camera/scripts/stop-preview-hd.sh
```

只支持一个持续预览客户端，不要同时开多个页面或一边运行接收测试一边打开直播。服务只绑定 USB IP；没有改 Wi-Fi/防火墙/自启/系统库。原有 8080 缩略预览已停止，不应与高清入口同时使用。

## 原始对照与问题边界

`hd-baseline-1792332445/30/`：原生 2560×1440、实测 30 FPS，原始图细节可见，样本顶部未见高速档的彩色条纹。

`hd-baseline-1792332445/80/`：原生 1280×720、实测 82.3747 FPS，但原始 NV21 转换后的图已经存在顶部彩色条纹。硬件 JPEG 第一帧也出现同类条纹，排除仅由旧缩略或网页传输导致的解释。尚不能进一步断言是时序、ISP、驱动或硬件信号问题。

旧版 320×180 缩略预览的模糊是实现中的主动降采样造成的，不是摄像头只能输出该清晰度。新版不缩小画幅，直接将原 VI 帧交给硬件 MJPEG，Qfactor=85。该质量参数是本次保守默认，不代表无损。

## 验证及失败记录

`preview-hd-first-attempt.log`：首次将编码输入率误设为传感器 80 FPS，而应用已经先抽帧，触发 `0xc0078041`，按当前 SDK 枚举为 `CVI_ERR_VENC_FRC_NO_ENC`。已把编码输入率改成应用实际请求的 30，不改传感器档位。

随后同步硬件编码版本收到 1280×720、27.44 FPS 的连续 JPEG，未发生编码错误，但阻塞取帧，VI 实测约 56 FPS。为维持高速采集，最终版本将编码放到独立线程，待编码帧最多保留一张，旧待编码帧及时释放；编码完成后才释放正在使用的 VI 帧，避免复用产生撕裂，不无限排队。

最终实测以 `preview-hd-receive.json` 和 `preview-hd-run.log` 为准。未验证数小时长稳、镜头焦距/标定、严格光学逐帧唯一性、端到端毫秒延迟。高速档条纹未解决，不能宣称画质完全验收。

60 档独立编码线程版本已测：20 秒收到 496 帧、496 个不同 JPEG 哈希，1280×720，接收 24.730 FPS；VI 约 60 FPS，重复 PTS/超时/编码错误均为 0。`preview-hd-60-last.jpg` 本次样本未见 80 档顶部的彩色条纹；不能据单张图承诺全部边界或长期无瑕疵。清晰度较旧缩略方案恢复为完整 720P，但不等同于 1440P 的原生细节。`snapshot.jpg` 接口也已实际返回完整 JPEG。

80 档独立编码线程版本已测：20 秒收到 552 帧、552 个不同 JPEG 哈希，1280×720，接收 27.528 FPS；同时 VI 日志 host/PTS 约 82.5 FPS、零重复和超时、编码错误 0。已另存 `preview-hd-80-receive.json`、`preview-hd-80-run.log`、`preview-hd-80-last.jpg`。该统计不代表浏览器 80 FPS，也不代表条纹消失。

增加 60 档选项时尝试使用 lock-free `atomic<bool>` 管理多线程停止标志；交叉编译断言失败，确认目标工具链不保证 1 字节原子始终无锁，已改用 RISC-V 原生 32 位 `atomic<int>`，避免在信号处理函数中隐式加锁。这一失败没有部署到板端。

## 文件、命令与回退

新增：`camera_preview_hd.cpp`、`camera_preview_hd`、`build-preview-hd.sh`、`board-hd.py`、`check-preview-hd.py`、启停脚本、本说明、`build-preview-hd/` 对象文件、原始对照报告、接收 JSON/样本 JPEG、运行日志。板端只新增 `bin/camera_preview_hd`、两个独立启停脚本和报告。原工程的 common/驱动源码、原采集二进制、配置和系统库未修改。没有删除或移动文件。

执行：只读源码/资料检索；`board-preview80.py stop` 停旧预览；`board-hd.py baseline` 调用原 benchmark 并用板端已有 ffmpeg 转全尺寸样本；WSL `bash build-preview-hd.sh` 构建；`sh -n` 和 Python AST 检查；`board-hd.py deploy/status/stop`；`check-preview-hd.py` 有界接收测试。没有安装依赖或执行 Git 操作。

资料获取过程中两条猜测的 main 分支原始链接 404，已通过仓库当前目录确定社区源码在 master 分支。WSL 仍提示现有失效的 F 盘 PATH 项和 `.wslconfig` 警告，未修改环境。

停止高清预览即回退到原功能，无需刷机、恢复驱动或替换库。锁会正常释放，原 `scripts/benchmark.sh 80 60` 仍保留。若出现故障，先查看 `tail -20 "$(cat /code/camera/run/preview-hd.report)/run.log"`，不要删除锁或盲目重复启动。仅验证本块 RISC-V 板卡及当前镜像，未声称其他平台兼容。
