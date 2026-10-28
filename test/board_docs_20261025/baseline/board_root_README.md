# GC4653 摄像头测试与复现（2026-10-07）
先看 docs/RESULTS.md。所有摄像头实验均放在 /code/camera 内。

## 实测结果
- 原驱动 2560×1440：30.000 FPS。
- MaixCDK 高速驱动 1280×720，60 档：59.900 FPS（20 秒）。
- MaixCDK 高速驱动 1280×720，80 档：82.400 FPS（20 秒）；82.333 FPS（60 秒）。
- 以上为 VI 实际取帧速度，采用单调时钟及每帧 PTS 双重计算，不是配置里的 FPS 数字。
- 长测没有重复 PTS、取帧超时、CSI 溢出；有少量较长帧间隔，详见 CSV。
- 画面验证：最初原驱动抓拍正常，之后高速和原驱动复测均变暗。尚未排除镜头遮挡/环境变化，不能把高速模式的画质验收写成通过。
- 82.33 FPS 是本次已测到的高速结果，不是传感器的绝对最大值，也不是浏览器预览帧率。

## 快速使用（在荔枝派上）
```sh
cd /code/camera
./scripts/benchmark.sh 30 20
./scripts/benchmark.sh 60 20
./scripts/benchmark.sh 80 60
./scripts/status.sh
```
每次生成独立 reports/user-模式-开机秒数-PID 目录，包含 run.log、frames.csv、result.json、VI/CSI 状态、frame.nv21 及内存记录。
程序定时结束；Ctrl+C 或另一终端 ./scripts/stop.sh 会请求正常清理。
不要 kill -9，也不要运行 archive/previous-launcher/start.sh。
目录名采用开机秒数，因为板子系统时钟未校准。

## 查看样本
```sh
./scripts/make_preview.sh /code/camera/reports/05-maix-80 1280x720
```
生成同目录 frame.jpg（640×360）。原始 NV21 保留传感器输出尺寸。
此次没有启动 HTTP/MJPEG 服务，网页预览需要后续编码与网络服务。

## 目录
- bin/：原生 C++ 测试程序，基线、新驱动、AE 诊断三个版本。
- src/camera_bench.cpp：取帧、统计、样本保存、正常释放逻辑。
- src/atomic_compat.c：适配当前镜像 libisp.so 所需的原子操作符号。
- src/common/：官方 SDK 的公共初始化源码。
- src/sensor_baseline/：当前官方 Build SDK 的原 GC4653 驱动。
- src/sensor/：MaixCDK GC4653 驱动原始副本（包含 720P 模式和官方高速时钟选择）。
- src/sensor_ae_fix/：按当前模式选择 AE 参数的诊断版本，不作为默认推荐。
- scripts/：板端独立测试、状态查看、安全停止、预览图转换入口。
- configs/sensor_cfg.original.ini：系统摄像头配置的副本，系统原文件未修改。
- reports/：成功及失败实验记录。
- docs/：详细结果、源码来源、交叉编译与限制说明。
- archive/previous-launcher/：之前启动脚本的备份，不要运行。
- run/：测试期间 PID 与互斥锁，正常结束后自动移除。

## 交叉编译
电脑端构建工程统一保存在 WSL：
/home/admin123/projects/LicheeRV/crossCompiling/camera
官方 SDK 和工具链保存在同级 LicheeRV-Nano-Build。
使用官方 riscv64-unknown-linux-musl GCC 10.2.0；动态使用板端原有 CVI 运行库，未替换系统库。
WSL 执行：
```sh
cd /home/admin123/projects/LicheeRV/crossCompiling/camera
bash build.sh
```
Docker 引擎本次仍不可连接，尚未验证容器内构建。此次二进制实际在 WSL 官方工具链中构建成功并在板端运行。
不需要在板端安装编译器。板端 src 是可阅读与追溯的源码副本，完整构建所需 SDK 在 WSL。
