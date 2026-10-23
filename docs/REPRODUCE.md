# 环境与复现说明

**重要：** 整个项目以 LicheeRV Nano (SG2002) + GC4653 模组为前提。板端 CVITEK MMF、ISP、驱动、设备树、kernel 必须与程序编译环境匹配。不要在正在使用摄像头的设备上直接执行实验程序。

## 1. 先验证硬件、地址与工作状态

通过 USB 数据线连接，Windows PowerShell：

```powershell
ssh root@10.133.124.1
```

上述 USB NCM IP 是原试验环境的样例，其他板端 IP 需按网络状况替换。检查：

```sh
uname -a
cat /proc/device-tree/model
cat /sys/class/thermal/thermal_zone0/temp
cat /proc/mipi-rx
ps w | grep '[c]amera'
test ! -d /code/camera/run/lock && echo FREE
```

不要因 SSH 可连就假设 sensor 设备未被占用。只有锁空闲、端口 8081 未被其他服务占用、CPU 温度合适时才考虑启动。

## 2. 复现较成熟的原有 70 FPS 档

自研版本：

- [70.69 FPS 独立源码](../test/over70_lab/candidate_70p7/source/)
- [112秒长测与问题边界](../test/over70_lab/RESULTS_70FPS_20261019.md)
- [自动验证工具](../test/over70_lab/run_lab.py)
- [2026-10-22 再次启动与停止方法](../test/view70_20261022/RUN_STATUS.md)

**关键参数：** MCLK=27 MHz、1920×1080、HTS=1180、VTS=1200。代码路径保留了 `LICHEE_TEST_HTS` / `LICHEE_TEST_VTS` 参数入口。不同板子不能假定把这个参数复制过去即可稳定达到 70 FPS。

板端运行（只做示例，正式执行前请确认实际程序路径/链接库、是否已持有互斥锁）：

```sh
cd /code/camera
env LICHEE_TEST_HTS=1180 LICHEE_TEST_VTS=1200 \
    PREVIEW_FACTORY_QUALITY=90 \
    LD_LIBRARY_PATH=/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd \
    /tmp/<YOUR_BINARY>/camera_factory_timing 10.133.124.1 /tmp/<YOUR_REPORT_DIR> 60
```

该程序占用相机独占资源并提供 8081 HTTP JPEG 端口。参数 `60` 是 sensor 驱动使用的模式选择，不代表实测帧率上限；具体以采集日志 `host_fps`、`pts_fps` 为准。需先编译好适配板端的 RISC-V 程序并将其部署到临时目录。

## 3. 网页查看与停止

当该程序正常启动、网络可达：

- 主页面：`http://10.133.124.1:8081/`
- 单张抓拍：`http://10.133.124.1:8081/snapshot.jpg`
- MJPEG 流：`http://10.133.124.1:8081/live.mjpg`

网页端可能受 USB 速度、JPEG 体积与浏览器刷新率限制。不要同时打开多个长连接，不要用接收 FPS 冒充屏幕显示 FPS。

终止后要确认进程已退出，才释放**本次运行创建的**互斥锁。不要使用 `kill -9`，不要直接删除别的进程锁目录。

## 4. 精确测量和验收

- FPS：至少采集 60 秒，记录相同帧序列的主机测量与 PTS 估算。
- MIPI：`/proc/mipi-rx` 中 EccErr / CrcErr / HdrErr / WcErr / FIFO 不得在稳定窗口新增。
- RAW/NV21：检查数据长度、像素格式、亮暗场、彩条、坏行以及不同帧是否真正来自独立曝光。
- 温度：`/sys/class/thermal/thermal_zone0/temp` 为 SoC 温度，不是 CMOS 结温；安全阈值应按实际硬件确认。
- 失败保留：能取到数据但出现 CRC 或 Bayer 顶部条纹的模式按失败记录，**不得覆盖已保存的稳定基线**。

## 5. 交叉编译

- 项目内含大量历史实验代码、`build.sh`、`rebuild-main.sh` 和源文件。
- 官方 SDK/交叉工具链过大，且需遵守各自版权许可，**不通过此 Git 仓库二次打包分发**。
- 请按官方 [Sipeed LicheeRV Nano Build 仓库](https://github.com/sipeed/LicheeRV-Nano-Build) 提供的匹配版本部署编译器和 MMF 头文件。
- 历史脚本可能使用绝对路径，请在新的编译环境中审阅并适配，不要盲目执行针对其他设备配置的 kernel/boot 操作。`n