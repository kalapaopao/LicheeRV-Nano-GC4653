# 2026-10-19 续测：接近70 FPS与36 MHz 驱动路线

本次写入均限制在电脑 **D:\study\LicheeRV\test** 下；原有研究文件只读且未覆盖。板端仅在 /tmp 写独立测试程序/图片，测试后清理自己创建的临时目录，没有修改 /mnt/system/ko、摄像头驱动、固件和原预览脚本。

## 1. 新增实测：1920×1080、27 MHz、HTS=1200

使用独立副本 `factory_midhts/`（从 `factory_timing/` 拷贝，未修改旧工程），尝试了更靠近失败边界的 HTS。

| 实验目录 | HTS | 采集FPS | PTS FPS | MIPI ECC/CRC/Hdr/Wc/FIFO | 重复PTS /超时/编码错误 | NV21顶部异常比 | 状态 |
|---|---:|---:|---:|---|---|---:|---|
| results/1080-midhts-20261019-175936 | 1190 | 69.7110 | 69.7107 | 0/0/0/**1**/0 | 0/0/0 | 0.961 | **拒绝**：出现1次word-count错误 |
| results/1080-midhts-20261019-180048 | 1200 | 69.5709 | 69.5706 | 0/0/0/0/0 | 0/0/0 | 0.948 | 约14秒短测通过 |
| results/1080-midhts-20261019-180211 | 1200 | **69.5319** | 69.5320 | 0/0/0/0/0 | 0/0/0 | 2.326 | **45秒/2507帧**稳定性抽检通过 |

每次原生 NV21 长度 3,110,400 字节（1920×1080 NV21），图片原始样本、统计日志与 MIPI 快照在对应结果目录中。顶行异常比定义为顶部1～9行的最大Y分量相邻行平均差 / 第21～80行的差值中位数；历史坏模式远超这一正常范围。注意此程序每次仅存首个原始NV21样本，并非逐帧图像全区域无损验收；45秒只是短期稳定运行而不是量产级认证，也没有证明ISP前 Bayer RAW 对每帧均正常。

**这轮保留的最靠谱档是 HTS=1200、约69.5FPS**，不是数值略高却发生MIPI WcErr的1190。继续缩短HTS不符合GC4653手册对行长寄存器的谨慎说明，也已出现实际接收错误，已按规定停止1170及1160档。

对应源码：`factory_midhts/sensor/gc4653_sensor_ctl.c`，程序：`factory_midhts/camera_factory_timing`，自动执行器：`run_1080_midhts.py`、`run_1080_midhts_1200_control.py`、`run_1080_midhts_1200_long.py`。

## 2. 为720P、80+ FPS准备的36 MHz合法MCLK分支

已定位本机真实的soph_mipi_rx.ko使用的内核 `5.10.4-tag- #10`。Sipeed官方BSP `sipeed/LicheeRV-Nano-Build` 的源码里，`osdrv/interdrv/v2/cif/Makefile`输出模块名确为 **soph_mipi_rx**（比通用SOPHGO osdrv的 cvi_mipi_rx 更匹配此板）。所查Git提交 d4003f1，日期2026-01-14；板端Linux编译时间2025-12-29，所以**代码相近不等于完全ABI兼容**。

- `kernel36/sipeed_patch-src/cif.c`、`cif_uapi.h`、`sipeed_soph_mipi_rx_36mhz.patch`：Sipeed专用的36MHz改动，在原枚举末尾增加数值6，不挪动已有选项；在CCF分支新增36,000,000Hz，并进行round/set/get/错误回退与运行状态保护。
- 补丁已离线在 test/kernel36/patch_check 中试验应用成功，提取的源码逻辑内容与补丁应用后内容一致。补丁是可审核源码，不是已构建或可直接加载的.ko。
- `minraw36/minraw36`：已交叉编译成功，RISC-V 720P简化Bayer RAW程序，只允许27/36MHz，无37.125MHz模式。先前此**同一程序在旧驱动的27MHz模式**通过8秒481帧、60.00FPS、3张正确RAW12基线，记录于 `results/spec27-hts-20261019-171906/`。
- `kernel36/board_reference/soph_mipi_rx.original.ko`：本次只读备份的原模块，SHA256=27aec4b153561e51446d178ba7788d32301b0a55fb91032ee07dbf2e23b05a00；`board.config`为板端 /proc/config.gz 提取的内核配置，均不替换板端文件。
- 已看到板端时钟树 CAM1来自~1.188GHz父PLL，可配置分频；整数÷33理论等于35,999,999.64Hz，落在GC4653公开最大输入时钟36MHz以下，但**具体硬件输出和80FPS帧率至今未上板验证**。

## 3. 仍未能加载36MHz内核模块的原因

- 下载到的WSL为精简Ubuntu22.04，主机编译器未安装。隔离于 `test/kernel36/host_tools` 已下载和解包GNU Make及GCC11等工具（未运行系统apt install），用于构建环境，探针/编译器头文件路径仍在调整。
- Sipeed BSP包含 Linux 在Windows保留的 `aux.c`、`aux.h` 文件名，Windows Git直接checkout失败；尝试 WSL git archive 按目录提取Linux头文件与脚本，但远端部分Git blob下载/读取超过等待时间后中止。临时来源仓库、尝试文件仅在 `test/vendor_sipeed_* ` 和 `test/kernel36`，没有修改旧研究成果。
- 没有生成与当前Kernel vermagic及soph_base依赖完全匹配的新 `soph_mipi_rx.ko`，**因此未进行rmmod、insmod、驱动覆盖、闪存写入、内核寄存器直写**；无36MHz实测帧率或无条纹结论。

## 4. 接下来要真正攻克80+ FPS

优先恢复对应内核的完整匹配源码、Kbuild/host GCC/内核符号，离线编译并校验新.ko的vermagic、模块名、依赖、symbol CRC和卸载/恢复方案，再安排安全的27→36→27 RAW-only对照。若在规格内36MHz仍出现相同RAW顶部问题，则同步查MIPI RX错误、GC4653芯片PLL/ADC读出时序或替换摄像头模组。不建议继续通过减HTS或把37.125MHz合法化绕过诊断。需要实测输出时钟的频率/抖动/占空比与供电电平，避免将软件读回当成电气质量确认。

## 5. 最终设备和数据安全状态

2026-10-19本轮结束时，SSH复核相机互斥锁空闲，`clk_cam1`为27,000,000Hz，板端无独立实验进程。当前原预览按照本轮开始前状态保持关闭。全部3组1080P原始NV21、截图和日志均保留在本地`test/results`，确认拷贝成功后只清理板端本轮自己创建的 `/tmp/lichee-midhts-*` 三个临时目录；`/tmp`恢复约63.5MiB可用。未修改或删除用户原有文件。
